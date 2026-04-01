import pytest

from cartography.tenancy.models import Tenant
from cartography.tenancy.models import TenantConfig


class TestTenant:
    def test_create_valid_tenant(self):
        t = Tenant(id="acme", name="Acme Corp")
        assert t.id == "acme"
        assert t.name == "Acme Corp"
        assert t.neo4j_database is None
        assert t.label_prefix is None

    def test_tenant_with_all_fields(self):
        t = Tenant(
            id="acme-1",
            name="Acme Corp",
            neo4j_database="neo4j_acme",
            label_prefix="Org",
        )
        assert t.neo4j_database == "neo4j_acme"
        assert t.label_prefix == "Org"

    def test_tenant_label_default(self):
        t = Tenant(id="acme", name="Acme Corp")
        assert t.tenant_label == "Tenant_acme"

    def test_tenant_label_custom_prefix(self):
        t = Tenant(id="acme", name="Acme Corp", label_prefix="Org")
        assert t.tenant_label == "Org_acme"

    def test_empty_id_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            Tenant(id="", name="Acme Corp")

    def test_invalid_id_raises(self):
        with pytest.raises(ValueError, match="invalid"):
            Tenant(id="acme corp!", name="Acme Corp")

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            Tenant(id="acme", name="")

    def test_id_allows_hyphens_and_underscores(self):
        t = Tenant(id="acme-corp_1", name="Acme Corp")
        assert t.id == "acme-corp_1"


class TestTenantConfig:
    def test_default_config(self):
        cfg = TenantConfig()
        assert cfg.isolation_mode == "label"
        assert cfg.tenants == []

    def test_label_mode(self):
        t = Tenant(id="t1", name="Tenant 1")
        cfg = TenantConfig(isolation_mode="label", tenants=[t])
        assert cfg.isolation_mode == "label"
        assert len(cfg.tenants) == 1

    def test_database_mode(self):
        t = Tenant(id="t1", name="Tenant 1", neo4j_database="db_t1")
        cfg = TenantConfig(isolation_mode="database", tenants=[t])
        assert cfg.isolation_mode == "database"

    def test_invalid_isolation_mode_raises(self):
        with pytest.raises(ValueError, match="Invalid isolation_mode"):
            TenantConfig(isolation_mode="invalid")  # type: ignore[arg-type]

    def test_duplicate_tenant_ids_raises(self):
        t1 = Tenant(id="acme", name="Acme A")
        t2 = Tenant(id="acme", name="Acme B")
        with pytest.raises(ValueError, match="Duplicate tenant ids"):
            TenantConfig(tenants=[t1, t2])
