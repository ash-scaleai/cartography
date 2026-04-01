from __future__ import annotations

import logging
from typing import Any
from typing import Optional

from cartography.observability.config import ObservabilityConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
_meter: Any = None

# Pre-defined instruments (set by init_metrics)
_records_ingested: Any = None
_sync_duration: Any = None
_api_errors: Any = None


# ---------------------------------------------------------------------------
# No-op fallbacks
# ---------------------------------------------------------------------------


class _NoOpCounter:
    """Minimal stand-in for an OpenTelemetry Counter."""

    def add(self, amount: int, attributes: Optional[dict[str, str]] = None) -> None:
        pass


class _NoOpHistogram:
    """Minimal stand-in for an OpenTelemetry Histogram."""

    def record(self, value: float, attributes: Optional[dict[str, str]] = None) -> None:
        pass


class _NoOpMeter:
    """Minimal stand-in for an OpenTelemetry Meter."""

    def create_counter(self, name: str, **kwargs: Any) -> _NoOpCounter:
        return _NoOpCounter()

    def create_histogram(self, name: str, **kwargs: Any) -> _NoOpHistogram:
        return _NoOpHistogram()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def init_metrics(config: Optional[ObservabilityConfig] = None) -> Any:
    """Initialise the global meter and predefined instruments.

    If *config* is ``None``, observability is disabled, or the
    ``opentelemetry`` packages are not installed, lightweight no-op
    instruments are created.

    Args:
        config: Observability configuration.

    Returns:
        An OpenTelemetry ``Meter`` or a :class:`_NoOpMeter`.
    """
    global _meter, _records_ingested, _sync_duration, _api_errors

    if config is None or not config.enabled or not config.otlp_endpoint:
        _meter = _NoOpMeter()
        _records_ingested = _meter.create_counter("cartography_records_ingested")
        _sync_duration = _meter.create_histogram("cartography_sync_duration_seconds")
        _api_errors = _meter.create_counter("cartography_api_errors_total")
        return _meter

    try:
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter,
        )
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource
    except ImportError:
        logger.debug(
            "OpenTelemetry metrics packages are not installed; "
            "falling back to no-op meter.",
        )
        _meter = _NoOpMeter()
        _records_ingested = _meter.create_counter("cartography_records_ingested")
        _sync_duration = _meter.create_histogram("cartography_sync_duration_seconds")
        _api_errors = _meter.create_counter("cartography_api_errors_total")
        return _meter

    resource = Resource.create({"service.name": config.service_name})
    exporter = OTLPMetricExporter(endpoint=config.otlp_endpoint)
    reader = PeriodicExportingMetricReader(exporter)
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    _meter = provider.get_meter(config.service_name)

    _records_ingested = _meter.create_counter(
        name="cartography_records_ingested",
        description="Total number of records ingested by cartography",
        unit="1",
    )
    _sync_duration = _meter.create_histogram(
        name="cartography_sync_duration_seconds",
        description="Duration of cartography sync operations in seconds",
        unit="s",
    )
    _api_errors = _meter.create_counter(
        name="cartography_api_errors_total",
        description="Total number of API errors encountered during sync",
        unit="1",
    )
    return _meter


def get_meter() -> Any:
    """Return the current meter (no-op if :func:`init_metrics` has not been called)."""
    global _meter
    if _meter is None:
        _meter = _NoOpMeter()
    return _meter


def record_ingestion(module: str, count: int) -> None:
    """Record *count* records ingested for *module*."""
    global _records_ingested
    if _records_ingested is None:
        return
    _records_ingested.add(count, attributes={"module": module})


def record_sync_duration(module: str, seconds: float) -> None:
    """Record sync duration in *seconds* for *module*."""
    global _sync_duration
    if _sync_duration is None:
        return
    _sync_duration.record(seconds, attributes={"module": module})


def record_api_error(module: str) -> None:
    """Increment API error counter for *module*."""
    global _api_errors
    if _api_errors is None:
        return
    _api_errors.add(1, attributes={"module": module})
