from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from cartography.tenancy.isolation import DatabaseIsolator
from cartography.tenancy.isolation import LabelIsolator
from cartography.tenancy.isolation import TenantIsolator
from cartography.tenancy.models import Tenant
from cartography.tenancy.models import TenantConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_tenant(**kwargs):
    defaults = {"id": "acme", "name": "Acme Corp"}
    defaults.update(kwargs)
    return Tenant(**defaults)


# ---------------------------------------------------------------------------
# LabelIsolator
# ---------------------------------------------------------------------------

class TestLabelIsolator:
    def test_scope_query_adds_tenant_label(self):
        isolator = LabelIsolator()
        tenant = _make_tenant()
        query = "MATCH (n:AWSAccount) RETURN n"
        scoped = isolator.scope_query(query, tenant)
        assert ":AWSAccount:Tenant_acme" in scoped

    def test_scope_query_multiple_match_clauses(self):
        isolator = LabelIsolator()
        tenant = _make_tenant()
        query = "MATCH (a:AWSAccount) MATCH (b:EC2Instance) RETURN a, b"
        scoped = isolator.scope_query(query, tenant)
        assert ":AWSAccount:Tenant_acme" in scoped
        assert ":EC2Instance:Tenant_acme" in scoped

    def test_scope_query_does_not_double_add(self):
        isolator = LabelIsolator()
        tenant = _make_tenant()
        query = "MATCH (n:AWSAccount:Tenant_acme) RETURN n"
        scoped = isolator.scope_query(query, tenant)
        # Should not add it a second time.
        assert scoped.count("Tenant_acme") == 1

    def test_scope_query_preserves_properties(self):
        isolator = LabelIsolator()
        tenant = _make_tenant()
        query = "MATCH (n:AWSAccount {id: $account_id}) RETURN n"
        scoped = isolator.scope_query(query, tenant)
        assert ":AWSAccount:Tenant_acme" in scoped
        assert "{id: $account_id}" in scoped

    def test_scope_query_custom_label_prefix(self):
        isolator = LabelIsolator()
        tenant = _make_tenant(label_prefix="Org")
        query = "MATCH (n:AWSAccount) RETURN n"
        scoped = isolator.scope_query(query, tenant)
        assert ":AWSAccount:Org_acme" in scoped

    def test_get_session_uses_default_database(self):
        isolator = LabelIsolator()
        tenant = _make_tenant()
        driver = MagicMock()
        isolator.get_session(driver, tenant)
        driver.session.assert_called_once_with()

    def test_scope_cleanup_adds_tenant_info(self):
        isolator = LabelIsolator()
        tenant = _make_tenant()
        params = {"UPDATE_TAG": 123}
        scoped = isolator.scope_cleanup(params, tenant)
        assert scoped["TENANT_ID"] == "acme"
        assert scoped["TENANT_LABEL"] == "Tenant_acme"
        # Original should not be mutated.
        assert "TENANT_ID" not in params

    def test_scope_cleanup_does_not_mutate_original(self):
        isolator = LabelIsolator()
        tenant = _make_tenant()
        original = {"UPDATE_TAG": 999}
        isolator.scope_cleanup(original, tenant)
        assert "TENANT_ID" not in original


# ---------------------------------------------------------------------------
# DatabaseIsolator
# ---------------------------------------------------------------------------

class TestDatabaseIsolator:
    def test_scope_query_unchanged(self):
        isolator = DatabaseIsolator()
        tenant = _make_tenant(neo4j_database="acme_db")
        query = "MATCH (n:AWSAccount) RETURN n"
        assert isolator.scope_query(query, tenant) == query

    def test_get_session_routes_to_tenant_database(self):
        isolator = DatabaseIsolator()
        tenant = _make_tenant(neo4j_database="acme_db")
        driver = MagicMock()
        isolator.get_session(driver, tenant)
        driver.session.assert_called_once_with(database="acme_db")

    def test_get_session_raises_when_no_database(self):
        isolator = DatabaseIsolator()
        tenant = _make_tenant()  # no neo4j_database
        driver = MagicMock()
        with pytest.raises(ValueError, match="does not have a neo4j_database"):
            isolator.get_session(driver, tenant)

    def test_scope_cleanup_adds_tenant_id(self):
        isolator = DatabaseIsolator()
        tenant = _make_tenant(neo4j_database="acme_db")
        params = {"UPDATE_TAG": 123}
        scoped = isolator.scope_cleanup(params, tenant)
        assert scoped["TENANT_ID"] == "acme"
        # Database isolator does not add TENANT_LABEL.
        assert "TENANT_LABEL" not in scoped


# ---------------------------------------------------------------------------
# TenantIsolator (facade)
# ---------------------------------------------------------------------------

class TestTenantIsolator:
    def test_label_mode_delegates_to_label_isolator(self):
        config = TenantConfig(isolation_mode="label")
        isolator = TenantIsolator(config)
        tenant = _make_tenant()
        query = "MATCH (n:AWSAccount) RETURN n"
        scoped = isolator.scope_query(query, tenant)
        assert "Tenant_acme" in scoped

    def test_database_mode_delegates_to_database_isolator(self):
        config = TenantConfig(isolation_mode="database")
        isolator = TenantIsolator(config)
        tenant = _make_tenant(neo4j_database="acme_db")
        query = "MATCH (n:AWSAccount) RETURN n"
        # Database mode should not modify the query.
        assert isolator.scope_query(query, tenant) == query

    def test_cleanup_tenant_a_does_not_affect_tenant_b(self):
        config = TenantConfig(isolation_mode="label")
        isolator = TenantIsolator(config)
        tenant_a = _make_tenant(id="tenant_a", name="Tenant A")
        tenant_b = _make_tenant(id="tenant_b", name="Tenant B")
        params = {"UPDATE_TAG": 1}

        scoped_a = isolator.scope_cleanup(params, tenant_a)
        scoped_b = isolator.scope_cleanup(params, tenant_b)

        assert scoped_a["TENANT_ID"] == "tenant_a"
        assert scoped_b["TENANT_ID"] == "tenant_b"
        assert scoped_a["TENANT_LABEL"] == "Tenant_tenant_a"
        assert scoped_b["TENANT_LABEL"] == "Tenant_tenant_b"
        # Originals untouched.
        assert "TENANT_ID" not in params

    def test_query_scoping_tenant_a_vs_b(self):
        config = TenantConfig(isolation_mode="label")
        isolator = TenantIsolator(config)
        tenant_a = _make_tenant(id="alpha", name="Alpha")
        tenant_b = _make_tenant(id="beta", name="Beta")
        query = "MATCH (n:EC2Instance) WHERE n.running = true RETURN n"

        scoped_a = isolator.scope_query(query, tenant_a)
        scoped_b = isolator.scope_query(query, tenant_b)

        assert "Tenant_alpha" in scoped_a
        assert "Tenant_beta" not in scoped_a
        assert "Tenant_beta" in scoped_b
        assert "Tenant_alpha" not in scoped_b
