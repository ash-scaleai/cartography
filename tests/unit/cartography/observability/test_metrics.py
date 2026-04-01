import sys
from unittest.mock import MagicMock
from unittest.mock import patch

from cartography.observability.config import ObservabilityConfig
from cartography.observability.metrics import _NoOpCounter
from cartography.observability.metrics import _NoOpHistogram
from cartography.observability.metrics import _NoOpMeter
from cartography.observability.metrics import get_meter
from cartography.observability.metrics import init_metrics
from cartography.observability.metrics import record_api_error
from cartography.observability.metrics import record_ingestion
from cartography.observability.metrics import record_sync_duration
import cartography.observability.metrics as metrics_mod


class TestInitMetricsNoOp:
    """init_metrics returns no-op meter when not configured."""

    def test_none_config(self):
        meter = init_metrics(None)
        assert isinstance(meter, _NoOpMeter)

    def test_disabled_config(self):
        cfg = ObservabilityConfig(enabled=False, otlp_endpoint="http://x:4317")
        meter = init_metrics(cfg)
        assert isinstance(meter, _NoOpMeter)

    def test_no_endpoint(self):
        cfg = ObservabilityConfig(enabled=True, otlp_endpoint=None)
        meter = init_metrics(cfg)
        assert isinstance(meter, _NoOpMeter)


class TestMetricsRecordNoOp:
    """Metric recording functions work without errors when not configured."""

    def setup_method(self):
        init_metrics(None)

    def test_record_ingestion_noop(self):
        # Should not raise
        record_ingestion("aws", 100)

    def test_record_sync_duration_noop(self):
        record_sync_duration("aws", 12.5)

    def test_record_api_error_noop(self):
        record_api_error("gcp")


class TestMetricsRecordConfigured:
    """Metric recording calls the underlying instruments when configured."""

    def test_record_ingestion_calls_add(self):
        mock_counter = MagicMock()
        metrics_mod._records_ingested = mock_counter
        record_ingestion("aws", 42)
        mock_counter.add.assert_called_once_with(42, attributes={"module": "aws"})

    def test_record_sync_duration_calls_record(self):
        mock_histogram = MagicMock()
        metrics_mod._sync_duration = mock_histogram
        record_sync_duration("gcp", 3.14)
        mock_histogram.record.assert_called_once_with(
            3.14, attributes={"module": "gcp"},
        )

    def test_record_api_error_calls_add(self):
        mock_counter = MagicMock()
        metrics_mod._api_errors = mock_counter
        record_api_error("github")
        mock_counter.add.assert_called_once_with(1, attributes={"module": "github"})


class TestGetMeter:
    """get_meter returns the current meter or a no-op."""

    def test_returns_noop_before_init(self):
        metrics_mod._meter = None
        meter = get_meter()
        assert isinstance(meter, _NoOpMeter)

    def test_returns_initialized_meter(self):
        init_metrics(None)
        meter = get_meter()
        assert isinstance(meter, _NoOpMeter)


class TestMetricsImportFallback:
    """init_metrics falls back to no-op when opentelemetry is not importable."""

    def test_import_error_fallback(self, monkeypatch):
        cfg = ObservabilityConfig(
            enabled=True,
            otlp_endpoint="http://localhost:4317",
        )

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
            meter = init_metrics(cfg)
            assert isinstance(meter, _NoOpMeter)
        finally:
            sys.modules.update(hidden)
