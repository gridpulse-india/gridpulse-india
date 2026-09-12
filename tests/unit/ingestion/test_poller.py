import json
import logging
from datetime import UTC, datetime
from io import StringIO

from services.ingestion.logging_config import JsonFormatter
from services.ingestion.models import CanonicalTelemetry
from services.ingestion.poller import Poller


class FakeClock:
    def __init__(self) -> None:
        self.current = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.current

    def perf_counter(self) -> float:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.current += seconds


def build_test_logger() -> tuple[
    logging.Logger,
    StringIO,
]:
    stream = StringIO()

    logger = logging.getLogger(f"test.poller.{id(stream)}")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())

    logger.addHandler(handler)

    return logger, stream


def read_log_lines(
    stream: StringIO,
) -> list[dict[str, object]]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]


def sample_records() -> list[CanonicalTelemetry]:
    observed_at = datetime(
        2026,
        8,
        19,
        17,
        0,
        tzinfo=UTC,
    )

    return [
        CanonicalTelemetry(
            source="grid_india_nldc_psp",
            entity="all_india",
            metric="grid_frequency",
            value=50.01,
            unit="Hz",
            observed_at=observed_at,
        ),
        CanonicalTelemetry(
            source="grid_india_nldc_psp",
            entity="all_india",
            metric="demand_met",
            value=237892.0,
            unit="MW",
            observed_at=observed_at,
        ),
    ]


def test_success_log_contains_required_fields() -> None:
    logger, stream = build_test_logger()
    clock = FakeClock()

    poller = Poller(
        source="grid_india_nldc_psp",
        interval_seconds=60,
        poll_fn=sample_records,
        logger=logger,
        sleep_fn=clock.sleep,
        monotonic_fn=clock.monotonic,
        perf_counter_fn=clock.perf_counter,
    )

    assert poller.run_once() is True

    logs = read_log_lines(stream)

    assert len(logs) == 1

    event = logs[0]

    assert event["event"] == "poll_succeeded"
    assert event["source"] == "grid_india_nldc_psp"
    assert event["records_parsed"] == 2
    assert event["failures"] == 0
    assert "latency_ms" in event


def test_failure_is_logged_without_raising() -> None:
    logger, stream = build_test_logger()
    clock = FakeClock()

    def broken_poll() -> list[CanonicalTelemetry]:
        raise RuntimeError("simulated source failure")

    poller = Poller(
        source="grid_india_nldc_psp",
        interval_seconds=60,
        poll_fn=broken_poll,
        logger=logger,
        sleep_fn=clock.sleep,
        monotonic_fn=clock.monotonic,
        perf_counter_fn=clock.perf_counter,
    )

    assert poller.run_once() is False

    event = read_log_lines(stream)[0]

    assert event["event"] == "poll_failed"
    assert event["records_parsed"] == 0
    assert event["failures"] == 1
    assert event["error_type"] == "RuntimeError"
    assert event["error_message"] == "simulated source failure"


def test_scheduler_runs_repeatedly() -> None:
    logger, stream = build_test_logger()
    clock = FakeClock()

    poller = Poller(
        source="grid_india_nldc_psp",
        interval_seconds=60,
        poll_fn=sample_records,
        logger=logger,
        sleep_fn=clock.sleep,
        monotonic_fn=clock.monotonic,
        perf_counter_fn=clock.perf_counter,
    )

    runs = poller.run(
        max_runs=3,
    )

    assert runs == 3
    assert clock.sleeps == [
        60,
        60,
    ]

    events = [log["event"] for log in read_log_lines(stream)]

    assert events == [
        "poller_started",
        "poll_succeeded",
        "poll_succeeded",
        "poll_succeeded",
        "poller_stopped",
    ]


def test_scheduler_continues_after_failure() -> None:
    logger, stream = build_test_logger()
    clock = FakeClock()

    calls = 0

    def sometimes_failing_poll() -> list[CanonicalTelemetry]:
        nonlocal calls

        calls += 1

        if calls == 1:
            raise RuntimeError("temporary source failure")

        return sample_records()

    poller = Poller(
        source="grid_india_nldc_psp",
        interval_seconds=60,
        poll_fn=sometimes_failing_poll,
        logger=logger,
        sleep_fn=clock.sleep,
        monotonic_fn=clock.monotonic,
        perf_counter_fn=clock.perf_counter,
    )

    runs = poller.run(
        max_runs=2,
    )

    assert runs == 2
    assert calls == 2

    events = [log["event"] for log in read_log_lines(stream)]

    assert "poll_failed" in events
    assert "poll_succeeded" in events
