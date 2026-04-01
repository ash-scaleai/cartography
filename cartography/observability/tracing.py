from __future__ import annotations

import contextlib
import functools
import logging
from typing import Any
from typing import Callable
from typing import Generator
from typing import Optional
from typing import TypeVar

from cartography.observability.config import ObservabilityConfig

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
_tracer: Any = None  # Will hold an OpenTelemetry Tracer or a _NoOpTracer

# ---------------------------------------------------------------------------
# No-op fallbacks
# ---------------------------------------------------------------------------


class _NoOpSpan:
    """Minimal stand-in for an OpenTelemetry Span."""

    def set_attribute(self, key: str, value: Any) -> None:  # noqa: D401
        pass

    def set_status(self, *args: Any, **kwargs: Any) -> None:
        pass

    def record_exception(self, exception: BaseException) -> None:
        pass

    def end(self) -> None:
        pass

    def __enter__(self) -> "_NoOpSpan":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class _NoOpTracer:
    """Minimal stand-in for an OpenTelemetry Tracer."""

    def start_span(self, name: str, **kwargs: Any) -> _NoOpSpan:
        return _NoOpSpan()

    def start_as_current_span(self, name: str, **kwargs: Any) -> _NoOpSpan:
        return _NoOpSpan()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def init_tracer(config: Optional[ObservabilityConfig] = None) -> Any:
    """Initialise the global tracer.

    If *config* is ``None``, observability is disabled, or the
    ``opentelemetry`` packages are not installed, a lightweight no-op
    tracer is returned.  This ensures zero overhead in environments that
    do not opt into tracing.

    Args:
        config: Observability configuration.  Pass ``None`` to explicitly
            request a no-op tracer.

    Returns:
        An OpenTelemetry ``Tracer`` or a :class:`_NoOpTracer`.
    """
    global _tracer

    if config is None or not config.enabled or not config.otlp_endpoint:
        _tracer = _NoOpTracer()
        return _tracer

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.debug(
            "OpenTelemetry packages are not installed; falling back to no-op tracer.",
        )
        _tracer = _NoOpTracer()
        return _tracer

    resource = Resource.create({"service.name": config.service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=config.otlp_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(config.service_name)
    return _tracer


def get_tracer() -> Any:
    """Return the current tracer (no-op if :func:`init_tracer` has not been called)."""
    global _tracer
    if _tracer is None:
        _tracer = _NoOpTracer()
    return _tracer


class trace_sync:
    """Decorator **and** context-manager that wraps a sync operation in a span.

    Usage as a decorator::

        @trace_sync("aws")
        def start_aws_ingestion(neo4j_session, config):
            ...

    Usage as a context manager::

        with trace_sync("aws"):
            do_work()
    """

    def __init__(self, module_name: str) -> None:
        self.module_name = module_name

    # -- context-manager protocol ------------------------------------------

    def __enter__(self) -> Any:
        tracer = get_tracer()
        if isinstance(tracer, _NoOpTracer):
            self._span = _NoOpSpan()
        else:
            self._span = tracer.start_span(f"sync.{self.module_name}")
            self._span.set_attribute("cartography.module", self.module_name)
            # For real OTel spans we need to use the trace context manager.
            # We store the token so we can clean up in __exit__.
            try:
                from opentelemetry import context, trace
                ctx = trace.set_span_in_current_context(self._span)
                self._token = context.attach(ctx)
            except ImportError:
                self._token = None
        return self._span

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_val is not None and not isinstance(self._span, _NoOpSpan):
            self._span.record_exception(exc_val)
            try:
                from opentelemetry.trace import StatusCode
                self._span.set_status(StatusCode.ERROR, str(exc_val))
            except ImportError:
                pass
        self._span.end()
        if hasattr(self, "_token") and self._token is not None:
            try:
                from opentelemetry import context
                context.detach(self._token)
            except ImportError:
                pass

    # -- decorator protocol ------------------------------------------------

    def __call__(self, func: F) -> F:  # type: ignore[return]
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with trace_sync(self.module_name):
                return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]
