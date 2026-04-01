"""Isolation strategies for multi-tenant cartography deployments."""
from __future__ import annotations

import logging
import re
from typing import Any
from typing import Dict

import neo4j

from cartography.tenancy.models import Tenant
from cartography.tenancy.models import TenantConfig

logger = logging.getLogger(__name__)


class TenantIsolator:
    """Facade that delegates to the correct isolation strategy based on config."""

    def __init__(self, config: TenantConfig) -> None:
        self._config = config
        if config.isolation_mode == "database":
            self._strategy: _IsolationStrategy = DatabaseIsolator()
        else:
            self._strategy = LabelIsolator()

    def scope_query(self, query: str, tenant: Tenant) -> str:
        """Add tenant-specific filtering to a Cypher query.

        For *label*-based isolation this injects a ``WHERE`` clause (or augments
        an existing one) so that only nodes belonging to *tenant* are matched.
        For *database*-based isolation queries are returned unchanged because
        isolation is handled at the session level.
        """
        return self._strategy.scope_query(query, tenant)

    def get_session(self, driver: neo4j.Driver, tenant: Tenant) -> neo4j.Session:
        """Return a Neo4j session scoped to *tenant*.

        For *database* isolation the session is opened against the tenant's own
        database.  For *label* isolation the default database is used.
        """
        return self._strategy.get_session(driver, tenant)

    def scope_cleanup(
        self,
        common_job_parameters: Dict[str, Any],
        tenant: Tenant,
    ) -> Dict[str, Any]:
        """Return a *copy* of *common_job_parameters* enriched with tenant info.

        This ensures that cleanup jobs only remove data belonging to *tenant*.
        """
        return self._strategy.scope_cleanup(common_job_parameters, tenant)


# ---------------------------------------------------------------------------
# Internal strategies
# ---------------------------------------------------------------------------

class _IsolationStrategy:
    """Abstract base for isolation strategies."""

    def scope_query(self, query: str, tenant: Tenant) -> str:
        raise NotImplementedError

    def get_session(self, driver: neo4j.Driver, tenant: Tenant) -> neo4j.Session:
        raise NotImplementedError

    def scope_cleanup(
        self,
        common_job_parameters: Dict[str, Any],
        tenant: Tenant,
    ) -> Dict[str, Any]:
        raise NotImplementedError


class LabelIsolator(_IsolationStrategy):
    """Isolation via an extra Neo4j label on every node.

    Every node created for a tenant receives an additional label of the form
    ``Tenant_<id>`` (or ``<label_prefix>_<id>`` when configured).  Queries are
    rewritten so that every ``MATCH (n:SomeLabel)`` becomes
    ``MATCH (n:SomeLabel:Tenant_<id>)``.
    """

    # Regex to find MATCH clauses with node patterns like (n:Label) or (n:Label {prop: val})
    _MATCH_NODE_RE = re.compile(
        r'(?P<pre>MATCH\s*\()'          # "MATCH ("
        r'(?P<var>\w+)'                  # variable name
        r'(?P<labels>:\w+(?::\w+)*)'     # :Label or :Label1:Label2
        r'(?P<post>[^)]*\))',            # rest up to closing paren
        re.IGNORECASE,
    )

    def scope_query(self, query: str, tenant: Tenant) -> str:
        tenant_label = tenant.tenant_label

        def _add_label(match: re.Match) -> str:
            pre = match.group('pre')
            var = match.group('var')
            labels = match.group('labels')
            post = match.group('post')
            # Only add the tenant label if it is not already present.
            if f":{tenant_label}" not in labels:
                labels = f"{labels}:{tenant_label}"
            return f"{pre}{var}{labels}{post}"

        return self._MATCH_NODE_RE.sub(_add_label, query)

    def get_session(self, driver: neo4j.Driver, tenant: Tenant) -> neo4j.Session:
        # Label isolation uses the default database.
        return driver.session()

    def scope_cleanup(
        self,
        common_job_parameters: Dict[str, Any],
        tenant: Tenant,
    ) -> Dict[str, Any]:
        params = dict(common_job_parameters)
        params['TENANT_ID'] = tenant.id
        params['TENANT_LABEL'] = tenant.tenant_label
        return params


class DatabaseIsolator(_IsolationStrategy):
    """Isolation via separate Neo4j databases (Enterprise feature)."""

    def scope_query(self, query: str, tenant: Tenant) -> str:
        # No query rewriting needed -- isolation is at the session/database level.
        return query

    def get_session(self, driver: neo4j.Driver, tenant: Tenant) -> neo4j.Session:
        db = tenant.neo4j_database
        if not db:
            raise ValueError(
                f"Tenant '{tenant.id}' does not have a neo4j_database configured "
                "but database-level isolation is enabled.",
            )
        return driver.session(database=db)

    def scope_cleanup(
        self,
        common_job_parameters: Dict[str, Any],
        tenant: Tenant,
    ) -> Dict[str, Any]:
        params = dict(common_job_parameters)
        params['TENANT_ID'] = tenant.id
        return params
