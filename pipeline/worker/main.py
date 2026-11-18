"""FaultIQ worker entry point.

Phase 0 behaviour: wait for the database, then idle with a periodic heartbeat log.
Phase 6 replaces the idle loop with job claiming (SELECT ... FOR UPDATE SKIP LOCKED).
"""

import argparse
import logging
import signal
import threading
from collections.abc import Callable

import faultiq
from worker.config import WorkerSettings, get_settings
from worker.db import check_database, make_engine
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


def run(settings: WorkerSettings, stop: threading.Event, probe: Callable[[], bool]) -> int:
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

    while not stop.wait(settings.heartbeat_interval_seconds):
        logger.info("worker_heartbeat", extra={"database_ok": probe(), "queue": "not_implemented"})
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

    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    return run(settings, stop, probe)
