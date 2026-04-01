from cartography.observability.config import ObservabilityConfig


def test_default_config():
    """ObservabilityConfig defaults are sensible."""
    cfg = ObservabilityConfig()
    assert cfg.enabled is True
    assert cfg.otlp_endpoint is None
    assert cfg.service_name == "cartography"
    assert cfg.log_format == "text"


def test_from_env_defaults(monkeypatch):
    """from_env returns defaults when no env vars are set."""
    monkeypatch.delenv("CARTOGRAPHY_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("CARTOGRAPHY_LOG_FORMAT", raising=False)
    monkeypatch.delenv("CARTOGRAPHY_OBSERVABILITY_ENABLED", raising=False)
    monkeypatch.delenv("CARTOGRAPHY_SERVICE_NAME", raising=False)

    cfg = ObservabilityConfig.from_env()
    assert cfg.enabled is True
    assert cfg.otlp_endpoint is None
    assert cfg.log_format == "text"
    assert cfg.service_name == "cartography"


def test_from_env_with_values(monkeypatch):
    """from_env reads env vars correctly."""
    monkeypatch.setenv("CARTOGRAPHY_OTLP_ENDPOINT", "http://collector:4317")
    monkeypatch.setenv("CARTOGRAPHY_LOG_FORMAT", "json")
    monkeypatch.setenv("CARTOGRAPHY_SERVICE_NAME", "my-carto")
    monkeypatch.setenv("CARTOGRAPHY_OBSERVABILITY_ENABLED", "1")

    cfg = ObservabilityConfig.from_env()
    assert cfg.enabled is True
    assert cfg.otlp_endpoint == "http://collector:4317"
    assert cfg.log_format == "json"
    assert cfg.service_name == "my-carto"


def test_from_env_disabled(monkeypatch):
    """from_env respects CARTOGRAPHY_OBSERVABILITY_ENABLED=false."""
    monkeypatch.setenv("CARTOGRAPHY_OBSERVABILITY_ENABLED", "false")
    cfg = ObservabilityConfig.from_env()
    assert cfg.enabled is False

    monkeypatch.setenv("CARTOGRAPHY_OBSERVABILITY_ENABLED", "0")
    cfg = ObservabilityConfig.from_env()
    assert cfg.enabled is False
