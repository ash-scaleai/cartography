import importlib
import sys
from unittest.mock import MagicMock
from unittest.mock import patch

from cartography.observability.config import ObservabilityConfig
from cartography.observability.tracing import _NoOpSpan
from cartography.observability.tracing import _NoOpTracer
from cartography.observability.tracing import get_tracer
from cartography.observability.tracing import init_tracer
from cartography.observability.tracing import trace_sync
import cartography.observability.tracing as tracing_mod


class TestInitTracerNoOp:
    """init_tracer returns a no-op tracer when observability is not configured."""

    def test_none_config(self):
        tracer = init_tracer(None)
        assert isinstance(tracer, _NoOpTracer)

    def test_disabled_config(self):
        cfg = ObservabilityConfig(enabled=False, otlp_endpoint="http://x:4317")
        tracer = init_tracer(cfg)
        assert isinstance(tracer, _NoOpTracer)

    def test_no_endpoint(self):
        cfg = ObservabilityConfig(enabled=True, otlp_endpoint=None)
        tracer = init_tracer(cfg)
        assert isinstance(tracer, _NoOpTracer)


class TestInitTracerReal:
    """init_tracer creates a real tracer when fully configured (mocking OTLP exporter)."""

    def test_with_endpoint(self):
        """When OTel SDK + OTLP exporter are installed, a real tracer is returned."""
        try:
            from opentelemetry import trace as _trace  # noqa: F401
            from opentelemetry.sdk.trace import TracerProvider as _TP  # noqa: F401
            from opentelemetry.sdk.resources import Resource as _R  # noqa: F401
            from opentelemetry.sdk.trace.export import BatchSpanProcessor as _BSP  # noqa: F401
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # noqa: F401
                OTLPSpanExporter as _OTLP,
            )
        except ImportError:
            import pytest
            pytest.skip("opentelemetry OTLP exporter packages not installed")

        cfg = ObservabilityConfig(
            enabled=True,
            otlp_endpoint="http://localhost:4317",
            service_name="test-carto",
        )

        mock_exporter_instance = MagicMock()
        mock_processor_instance = MagicMock()

        with (
            patch(
                "opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter",
                return_value=mock_exporter_instance,
            ) as mock_exp_cls,
            patch(
                "opentelemetry.sdk.trace.export.BatchSpanProcessor",
                return_value=mock_processor_instance,
            ),
        ):
            tracer = init_tracer(cfg)
            assert not isinstance(tracer, _NoOpTracer)
            mock_exp_cls.assert_called_once_with(endpoint="http://localhost:4317")


class TestInitTracerImportFails:
    """init_tracer falls back to no-op when opentelemetry is not importable."""

    def test_import_error_fallback(self, monkeypatch):
        cfg = ObservabilityConfig(
            enabled=True,
            otlp_endpoint="http://localhost:4317",
        )
        # Temporarily hide opentelemetry modules
        hidden = {}
        for mod_name in list(sys.modules):
            if mod_name.startswith("opentelemetry"):
                hidden[mod_name] = sys.modules.pop(mod_name)

        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def _reject_otel(name, *args, **kwargs):
            if name.startswith("opentelemetry"):
                raise ImportError(f"Mocked: {name}")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", _reject_otel)
        try:
            # Need to re-execute the import path inside init_tracer
            tracer = init_tracer(cfg)
            assert isinstance(tracer, _NoOpTracer)
        finally:
            # Restore hidden modules
            sys.modules.update(hidden)


class TestGetTracer:
    """get_tracer returns the current tracer or a no-op."""

    def test_returns_noop_before_init(self):
        tracing_mod._tracer = None
        tracer = get_tracer()
        assert isinstance(tracer, _NoOpTracer)

    def test_returns_initialized_tracer(self):
        init_tracer(None)  # sets no-op
        tracer = get_tracer()
        assert isinstance(tracer, _NoOpTracer)


class TestTraceSyncDecorator:
    """trace_sync works as both decorator and context manager."""

    def test_as_context_manager(self):
        init_tracer(None)
        with trace_sync("test_module") as span:
            assert isinstance(span, _NoOpSpan)

    def test_as_decorator(self):
        init_tracer(None)

        @trace_sync("test_module")
        def my_func(x):
            return x + 1

        assert my_func(5) == 6

    def test_decorator_preserves_name(self):
        init_tracer(None)

        @trace_sync("mod")
        def my_named_func():
            pass

        assert my_named_func.__name__ == "my_named_func"

    def test_context_manager_exception_handling(self):
        init_tracer(None)
        try:
            with trace_sync("failing") as span:
                raise ValueError("boom")
        except ValueError:
            pass  # Expected -- span should have ended cleanly
