import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from cartography.config import Config
from cartography.tenancy.manager import TenantManager
from cartography.tenancy.models import Tenant
from cartography.tenancy.models import TenantConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tenant(**kwargs):
    defaults = {"id": "acme", "name": "Acme Corp"}
    defaults.update(kwargs)
    return Tenant(**defaults)


def _sample_config_dict():
    return {
        "isolation_mode": "label",
        "tenants": [
            {"id": "acme", "name": "Acme Corp"},
            {"id": "globex", "name": "Globex Inc"},
        ],
    }


# ---------------------------------------------------------------------------
# TenantManager.load_config
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_load_json_config(self, tmp_path):
        config_file = tmp_path / "tenants.json"
        config_file.write_text(json.dumps(_sample_config_dict()))

        cfg = TenantManager.load_config(config_file)
        assert cfg.isolation_mode == "label"
        assert len(cfg.tenants) == 2
        assert cfg.tenants[0].id == "acme"
        assert cfg.tenants[1].id == "globex"

    def test_load_json_config_database_mode(self, tmp_path):
        data = {
            "isolation_mode": "database",
            "tenants": [
                {"id": "acme", "name": "Acme", "neo4j_database": "db_acme"},
            ],
        }
        config_file = tmp_path / "tenants.json"
        config_file.write_text(json.dumps(data))

        cfg = TenantManager.load_config(config_file)
        assert cfg.isolation_mode == "database"
        assert cfg.tenants[0].neo4j_database == "db_acme"

    def test_load_defaults_name_to_id(self, tmp_path):
        data = {
            "isolation_mode": "label",
            "tenants": [{"id": "acme"}],
        }
        config_file = tmp_path / "tenants.json"
        config_file.write_text(json.dumps(data))

        cfg = TenantManager.load_config(config_file)
        assert cfg.tenants[0].name == "acme"


# ---------------------------------------------------------------------------
# Single-tenant (no config) mode
# ---------------------------------------------------------------------------

class TestSingleTenantMode:
    def test_no_config_is_not_multi_tenant(self):
        mgr = TenantManager()
        assert mgr.is_multi_tenant is False

    def test_no_config_tenants_is_empty(self):
        mgr = TenantManager()
        assert mgr.tenants == []

    def test_cleanup_noop_without_config(self):
        mgr = TenantManager()
        params = {"UPDATE_TAG": 1}
        result = mgr.cleanup_tenant(_make_tenant(), params)
        # Returns a copy with no tenant enrichment.
        assert result == {"UPDATE_TAG": 1}


# ---------------------------------------------------------------------------
# sync_tenant
# ---------------------------------------------------------------------------

class TestSyncTenant:
    def test_sync_tenant_calls_sync_run(self):
        tenant = _make_tenant()
        cfg = TenantConfig(isolation_mode="label", tenants=[tenant])
        mgr = TenantManager(cfg)

        mock_sync = MagicMock()
        mock_sync.run.return_value = 0
        mock_driver = MagicMock()
        mock_config = MagicMock(spec=Config)

        result = mgr.sync_tenant(tenant, mock_sync, mock_driver, mock_config)

        mock_sync.run.assert_called_once_with(mock_driver, mock_config)
        assert result == 0

    def test_sync_tenant_database_mode_overrides_config(self):
        tenant = _make_tenant(neo4j_database="acme_db")
        cfg = TenantConfig(isolation_mode="database", tenants=[tenant])
        mgr = TenantManager(cfg)

        mock_sync = MagicMock()
        mock_sync.run.return_value = 0
        mock_driver = MagicMock()
        mock_config = MagicMock(spec=Config)
        mock_config.neo4j_database = "original_db"

        mgr.sync_tenant(tenant, mock_sync, mock_driver, mock_config)

        assert mock_config.neo4j_database == "acme_db"

    def test_sync_tenant_raises_without_config(self):
        mgr = TenantManager()
        with pytest.raises(RuntimeError, match="no tenant config"):
            mgr.sync_tenant(
                _make_tenant(),
                MagicMock(),
                MagicMock(),
                MagicMock(spec=Config),
            )


# ---------------------------------------------------------------------------
# sync_all_tenants
# ---------------------------------------------------------------------------

class TestSyncAllTenants:
    def test_sync_all_tenants_iterates(self):
        t1 = _make_tenant(id="t1", name="T1")
        t2 = _make_tenant(id="t2", name="T2")
        cfg = TenantConfig(isolation_mode="label", tenants=[t1, t2])
        mgr = TenantManager(cfg)

        mock_sync = MagicMock()
        mock_sync.run.return_value = 0
        mock_driver = MagicMock()
        mock_config = MagicMock(spec=Config)

        results = mgr.sync_all_tenants(mock_sync, mock_driver, mock_config)

        assert results == {"t1": 0, "t2": 0}
        assert mock_sync.run.call_count == 2


# ---------------------------------------------------------------------------
# cleanup_tenant
# ---------------------------------------------------------------------------

class TestCleanupTenant:
    def test_cleanup_scopes_to_tenant(self):
        tenant = _make_tenant()
        cfg = TenantConfig(isolation_mode="label", tenants=[tenant])
        mgr = TenantManager(cfg)

        params = {"UPDATE_TAG": 42}
        scoped = mgr.cleanup_tenant(tenant, params)

        assert scoped["TENANT_ID"] == "acme"
        assert scoped["TENANT_LABEL"] == "Tenant_acme"
        assert scoped["UPDATE_TAG"] == 42

    def test_cleanup_tenant_a_does_not_affect_tenant_b(self):
        ta = _make_tenant(id="a", name="A")
        tb = _make_tenant(id="b", name="B")
        cfg = TenantConfig(isolation_mode="label", tenants=[ta, tb])
        mgr = TenantManager(cfg)

        params = {"UPDATE_TAG": 1}
        scoped_a = mgr.cleanup_tenant(ta, params)
        scoped_b = mgr.cleanup_tenant(tb, params)

        assert scoped_a["TENANT_ID"] == "a"
        assert scoped_b["TENANT_ID"] == "b"
        assert "TENANT_ID" not in params
