import logging
import time
from collections.abc import Callable

from services.ingestion.models import CanonicalTelemetry

PollFunction = Callable[[], list[CanonicalTelemetry]]


class Poller:
    def __init__(
        self,
        *,
        source: str,
        interval_seconds: float,
        poll_fn: PollFunction,
        logger: logging.Logger | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        monotonic_fn: Callable[[], float] = time.monotonic,
        perf_counter_fn: Callable[[], float] = time.perf_counter,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than zero")

        self.source = source
        self.interval_seconds = interval_seconds
        self.poll_fn = poll_fn
        self._logger = logger or logging.getLogger("gridpulse.ingestion.poller")
        self._sleep = sleep_fn
        self._monotonic = monotonic_fn
        self._perf_counter = perf_counter_fn

    def run_once(self) -> bool:
        started_at = self._perf_counter()

        try:
            records = self.poll_fn()
        except Exception as exc:
            latency_ms = (self._perf_counter() - started_at) * 1000

            self._logger.error(
                "poll_failed",
                extra={
                    "source": self.source,
                    "latency_ms": round(latency_ms, 3),
                    "records_parsed": 0,
                    "failures": 1,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
                exc_info=True,
            )

            return False

        latency_ms = (self._perf_counter() - started_at) * 1000

        self._logger.info(
            "poll_succeeded",
            extra={
                "source": self.source,
                "latency_ms": round(latency_ms, 3),
                "records_parsed": len(records),
                "failures": 0,
            },
        )

        return True

    def run(
        self,
        *,
        duration_seconds: float | None = None,
        max_runs: int | None = None,
    ) -> int:
        if duration_seconds is not None and duration_seconds <= 0:
            raise ValueError("duration_seconds must be greater than zero")

        if max_runs is not None and max_runs <= 0:
            raise ValueError("max_runs must be greater than zero")

        scheduler_started_at = self._monotonic()
        runs = 0

        self._logger.info(
            "poller_started",
            extra={
                "source": self.source,
                "interval_seconds": self.interval_seconds,
                "duration_seconds": duration_seconds,
                "max_runs": max_runs,
            },
        )

        try:
            while True:
                if max_runs is not None and runs >= max_runs:
                    break

                if duration_seconds is not None:
                    elapsed = self._monotonic() - scheduler_started_at

                    if elapsed >= duration_seconds:
                        break

                cycle_started_at = self._monotonic()

                self.run_once()
                runs += 1

                if max_runs is not None and runs >= max_runs:
                    break

                now = self._monotonic()

                if duration_seconds is not None:
                    remaining = duration_seconds - (now - scheduler_started_at)

                    if remaining <= 0:
                        break
                else:
                    remaining = None

                cycle_elapsed = now - cycle_started_at

                sleep_seconds = max(
                    0.0,
                    self.interval_seconds - cycle_elapsed,
                )

                if remaining is not None:
                    sleep_seconds = min(
                        sleep_seconds,
                        remaining,
                    )

                if sleep_seconds > 0:
                    self._sleep(sleep_seconds)

        finally:
            self._logger.info(
                "poller_stopped",
                extra={
                    "source": self.source,
                    "runs": runs,
                },
            )

        return runs
