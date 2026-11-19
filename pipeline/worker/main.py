"""FaultIQ worker entry point (ADR 0007, ADR 0024).

Waits for the database, then loops: recover jobs abandoned by a dead worker, claim the oldest
queued job (SELECT ... FOR UPDATE SKIP LOCKED), run it, repeat. When the queue is empty it polls
every `poll_interval_seconds`. SIGTERM finishes the current job, then exits.
"""

import argparse
import logging
import signal
import threading
import time
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import faultiq
from worker.config import WorkerSettings, get_settings
from worker.db import check_database, make_engine, recover_stale, worker_id
from worker.logging import configure_logging

logger = logging.getLogger("faultiq.worker")


def wait_for_database(
    probe: Callable[[], bool], stop: threading.Event, retry_seconds: float, max_attempts: int
) -> bool:
    for attempt in range(1, max_attempts + 1):
        if probe():
            logger.info("database_ready", extra={"attempt": attempt})
            return True
        logger.warning("database_unavailable", extra={"attempt": attempt})
        if stop.wait(retry_seconds):
            return False
    return False


def run(
    settings: WorkerSettings,
    stop: threading.Event,
    probe: Callable[[], bool],
    step: Callable[[], bool] | None = None,
) -> int:
    """`step` runs one job and returns False when there was nothing to do."""
    logger.info(
        "worker_starting",
        extra={
            "pipeline_version": faultiq.PIPELINE_VERSION,
            "app_version": faultiq.__version__,
            "environment": settings.app_env,
        },
    )
    if not wait_for_database(probe, stop, settings.poll_interval_seconds, max_attempts=30):
        if stop.is_set():
            logger.info("worker_stopped")
            return 0
        logger.error("worker_giving_up_database_unreachable")
        return 1

    next_heartbeat = time.monotonic() + settings.heartbeat_interval_seconds
    while not stop.is_set():
        busy = False
        try:
            busy = step() if step is not None else False
        except Exception:  # a database outage must not kill the worker; retry after a pause
            logger.exception("worker_step_failed")
        if time.monotonic() >= next_heartbeat:
            logger.info("worker_heartbeat", extra={"database_ok": probe()})
            next_heartbeat = time.monotonic() + settings.heartbeat_interval_seconds
        if not busy:
            stop.wait(settings.poll_interval_seconds)
    logger.info("worker_stopped")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FaultIQ analysis worker")
    parser.add_argument("--check", action="store_true", help="check DB connectivity and exit")
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level)
    engine = make_engine(settings.database_url)

    def probe() -> bool:
        return check_database(engine)

    if args.check:
        ok = probe()
        logger.info("worker_check", extra={"database_ok": ok})
        return 0 if ok else 1

    from faultiq.explain.models import ModelStore  # heavy ML imports only when running jobs
    from worker.jobs import process_one
    from worker.telemetry import configure_tracing

    provider = configure_tracing()
    store = ModelStore(Path(settings.model_dir))
    me = worker_id()
    timeout = timedelta(minutes=settings.job_timeout_minutes)

    def step() -> bool:
        recovered = recover_stale(engine, timeout)
        if recovered:
            logger.warning("jobs_requeued_after_timeout", extra={"count": recovered})
        return process_one(engine, store, settings, me)

    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    try:
        return run(settings, stop, probe, step)
    finally:
        provider.shutdown()
