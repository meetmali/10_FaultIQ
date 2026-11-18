import threading

import faultiq
from worker.config import WorkerSettings
from worker.main import run, wait_for_database


def _settings() -> WorkerSettings:
    return WorkerSettings(poll_interval_seconds=0.01, heartbeat_interval_seconds=0.01)


def test_wait_for_database_succeeds_after_retries() -> None:
    answers = iter([False, False, True])
    assert wait_for_database(lambda: next(answers), threading.Event(), 0.0, max_attempts=5)


def test_wait_for_database_gives_up() -> None:
    assert not wait_for_database(lambda: False, threading.Event(), 0.0, max_attempts=3)


def test_run_returns_error_when_database_never_available() -> None:
    assert run(_settings(), threading.Event(), probe=lambda: False) == 1


def test_run_stops_cleanly_on_signal() -> None:
    stop = threading.Event()
    calls = 0

    def probe() -> bool:
        nonlocal calls
        calls += 1
        if calls >= 3:  # DB ready, then two heartbeats, then shutdown requested
            stop.set()
        return True

    assert run(_settings(), stop, probe) == 0


def test_pipeline_version_is_declared() -> None:
    assert faultiq.PIPELINE_VERSION.count(".") == 2
