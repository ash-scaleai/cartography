"""Tenant lifecycle management: loading config, running syncs per-tenant."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from typing import Dict
from typing import Optional

import neo4j

from cartography.config import Config
from cartography.tenancy.isolation import TenantIsolator
from cartography.tenancy.models import Tenant
from cartography.tenancy.models import TenantConfig

logger = logging.getLogger(__name__)


class TenantManager:
    """Orchestrates multi-tenant sync and cleanup operations.

    In single-tenant mode (no config supplied) every public method is a
    transparent no-op so the rest of the codebase does not need to branch
    on tenancy support.
    """

    def __init__(self, tenant_config: Optional[TenantConfig] = None) -> None:
        self._config = tenant_config
        self._isolator: Optional[TenantIsolator] = (
            TenantIsolator(tenant_config) if tenant_config else None
        )

    @property
    def is_multi_tenant(self) -> bool:
        return self._config is not None and len(self._config.tenants) > 0

    @property
    def tenants(self) -> list[Tenant]:
        if self._config is None:
            return []
        return list(self._config.tenants)

    @property
    def isolator(self) -> Optional[TenantIsolator]:
        return self._isolator

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    @staticmethod
    def load_config(path: str | Path) -> TenantConfig:
        """Load a :class:`TenantConfig` from a JSON or YAML file.

        JSON is supported natively.  YAML requires the optional ``pyyaml``
        package.
        """
        path = Path(path)
        raw_text = path.read_text(encoding='utf-8')

        if path.suffix in ('.yaml', '.yml'):
            try:
                import yaml  # type: ignore[import-untyped]
            except ImportError as exc:
                raise ImportError(
                    "PyYAML is required to load YAML tenant config files.  "
                    "Install it with: pip install pyyaml",
                ) from exc
            data = yaml.safe_load(raw_text)
        else:
            data = json.loads(raw_text)

        return _parse_tenant_config(data)

    # ------------------------------------------------------------------
    # Sync helpers
    # ------------------------------------------------------------------

    def sync_tenant(
        self,
        tenant: Tenant,
        sync: Any,  # cartography.sync.Sync -- avoid circular import
        neo4j_driver: neo4j.Driver,
        config: Config,
    ) -> int:
        """Run a full sync scoped to *tenant*.

        The method:
        1. Obtains a tenant-scoped Neo4j session (or adjusts the config).
        2. Delegates to ``sync.run()``.
        """
        if self._isolator is None:
            raise RuntimeError("TenantManager has no tenant config; cannot scope sync.")

        logger.info("Starting sync for tenant '%s' (%s)", tenant.name, tenant.id)

        # For database isolation, override the config's neo4j_database.
        if self._config and self._config.isolation_mode == "database":
            config.neo4j_database = tenant.neo4j_database

        result = sync.run(neo4j_driver, config)
        logger.info(
            "Finished sync for tenant '%s' (%s) with exit code %d",
            tenant.name, tenant.id, result,
        )
        return result

    def sync_all_tenants(
        self,
        sync: Any,
        neo4j_driver: neo4j.Driver,
        config: Config,
    ) -> Dict[str, int]:
        """Run a sync for every configured tenant and return per-tenant exit codes.

        This iterates sequentially today but the signature is designed so that
        callers can parallelise in the future.
        """
        results: Dict[str, int] = {}
        for tenant in self.tenants:
            results[tenant.id] = self.sync_tenant(tenant, sync, neo4j_driver, config)
        return results

    def cleanup_tenant(
        self,
        tenant: Tenant,
        common_job_parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Return tenant-scoped cleanup parameters.

        The returned dict is safe to pass into cleanup jobs -- it will never
        touch data belonging to other tenants.
        """
        if self._isolator is None:
            return dict(common_job_parameters)
        return self._isolator.scope_cleanup(common_job_parameters, tenant)


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _parse_tenant_config(data: dict) -> TenantConfig:
    """Parse a raw dict (from JSON/YAML) into a :class:`TenantConfig`."""
    tenants = [
        Tenant(
            id=t['id'],
            name=t.get('name', t['id']),
            neo4j_database=t.get('neo4j_database'),
            label_prefix=t.get('label_prefix'),
        )
        for t in data.get('tenants', [])
    ]
    return TenantConfig(
        isolation_mode=data.get('isolation_mode', 'label'),
        tenants=tenants,
    )
