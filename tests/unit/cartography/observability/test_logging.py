import json
import logging

from cartography.observability.config import ObservabilityConfig
from cartography.observability.logging import CorrelationIdFilter
from cartography.observability.logging import generate_correlation_id
from cartography.observability.logging import get_correlation_id
from cartography.observability.logging import init_logging
import cartography.observability.logging as logging_mod


class TestCorrelationId:
    """Correlation ID generation and retrieval."""

    def test_generate_returns_string(self):
        cid = generate_correlation_id()
        assert isinstance(cid, str)
        assert len(cid) == 36  # UUID4 canonical form

    def test_get_after_generate(self):
        cid = generate_correlation_id()
        assert get_correlation_id() == cid

    def test_successive_ids_differ(self):
        id1 = generate_correlation_id()
        id2 = generate_correlation_id()
        assert id1 != id2


class TestCorrelationIdFilter:
    """CorrelationIdFilter injects correlation_id into log records."""

    def test_filter_adds_attribute(self):
        logging_mod._correlation_id = "test-corr-123"
        filt = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello", args=(), exc_info=None,
        )
        result = filt.filter(record)
        assert result is True
        assert record.correlation_id == "test-corr-123"  # type: ignore[attr-defined]

    def test_filter_empty_when_no_id(self):
        logging_mod._correlation_id = None
        filt = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello", args=(), exc_info=None,
        )
        filt.filter(record)
        assert record.correlation_id == ""  # type: ignore[attr-defined]


class TestInitLogging:
    """init_logging configures root logger correctly."""

    def test_init_with_none_config(self):
        """No crash when config is None."""
        root = logging.getLogger()
        original_filters = list(root.filters)
        init_logging(None)
        # Should have added a CorrelationIdFilter
        new_filters = [f for f in root.filters if f not in original_filters]
        assert any(isinstance(f, CorrelationIdFilter) for f in new_filters)
        # Clean up
        for f in new_filters:
            root.removeFilter(f)

    def test_init_disabled_config(self):
        """Disabled config still installs correlation filter."""
        cfg = ObservabilityConfig(enabled=False)
        root = logging.getLogger()
        original_filters = list(root.filters)
        init_logging(cfg)
        new_filters = [f for f in root.filters if f not in original_filters]
        assert any(isinstance(f, CorrelationIdFilter) for f in new_filters)
        for f in new_filters:
            root.removeFilter(f)


class TestJsonLogging:
    """Structured JSON logging format."""

    def test_json_format(self):
        """When log_format='json', log output is valid JSON with expected fields."""
        cfg = ObservabilityConfig(enabled=True, log_format="json")

        # Set up an isolated logger/handler to test formatting
        test_logger = logging.getLogger("test_json_logging_format")
        test_logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        test_logger.addHandler(handler)

        root = logging.getLogger()
        original_filters = list(root.filters)

        init_logging(cfg)

        # Generate a correlation ID so it shows up
        cid = generate_correlation_id()

        # The json formatter should have been applied to root handlers.
        # We'll manually apply to our test handler too.
        from cartography.observability.logging import _JsonFormatter
        handler.setFormatter(_JsonFormatter())

        # Also apply correlation filter to our handler's logger
        filt = CorrelationIdFilter()
        test_logger.addFilter(filt)

        # Capture output
        import io
        stream = io.StringIO()
        handler.stream = stream

        test_logger.info("test message for json")
        output = stream.getvalue().strip()
        parsed = json.loads(output)

        assert parsed["message"] == "test message for json"
        assert parsed["level"] == "INFO"
        assert parsed["correlation_id"] == cid
        assert "timestamp" in parsed
        assert "logger" in parsed

        # Clean up
        test_logger.removeHandler(handler)
        test_logger.removeFilter(filt)
        new_filters = [f for f in root.filters if f not in original_filters]
        for f in new_filters:
            root.removeFilter(f)


class TestZeroConfigStartup:
    """Cartography starts cleanly with zero observability configuration."""

    def test_all_init_with_defaults(self):
        """Calling all init functions with no config causes no errors."""
        from cartography.observability.tracing import init_tracer, _NoOpTracer
        from cartography.observability.metrics import init_metrics, _NoOpMeter

        tracer = init_tracer()
        assert isinstance(tracer, _NoOpTracer)

        meter = init_metrics()
        assert isinstance(meter, _NoOpMeter)

        root = logging.getLogger()
        original_filters = list(root.filters)
        init_logging()
        new_filters = [f for f in root.filters if f not in original_filters]
        for f in new_filters:
            root.removeFilter(f)
