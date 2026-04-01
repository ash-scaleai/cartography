"""Data models for multi-tenancy configuration."""
from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import field
from typing import List
from typing import Literal
from typing import Optional


_TENANT_ID_RE = re.compile(r'^[A-Za-z0-9_-]+$')


@dataclass(frozen=True)
class Tenant:
    """Represents a single tenant in a multi-tenant cartography deployment.

    Attributes:
        id: Unique identifier for the tenant.  Must be alphanumeric (plus ``-`` and ``_``).
        name: Human-readable display name.
        neo4j_database: For *database*-level isolation, the Neo4j database name to use.
            Only meaningful when ``TenantConfig.isolation_mode == "database"``.
        label_prefix: For *label*-based isolation, the prefix added to the tenant label.
            Defaults to ``Tenant_<id>`` when left as ``None``.
    """
    id: str
    name: str
    neo4j_database: Optional[str] = None
    label_prefix: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Tenant id must not be empty.")
        if not _TENANT_ID_RE.match(self.id):
            raise ValueError(
                f"Tenant id '{self.id}' is invalid.  Only alphanumeric characters, "
                "hyphens, and underscores are allowed.",
            )
        if not self.name:
            raise ValueError("Tenant name must not be empty.")

    @property
    def tenant_label(self) -> str:
        """Return the Neo4j label used for label-based isolation."""
        if self.label_prefix:
            return f"{self.label_prefix}_{self.id}"
        return f"Tenant_{self.id}"


@dataclass
class TenantConfig:
    """Top-level configuration object describing how multi-tenancy should work.

    Attributes:
        isolation_mode: Either ``"database"`` (each tenant gets its own Neo4j
            database) or ``"label"`` (all tenants share one database but nodes
            are tagged with a tenant label).
        tenants: The list of tenants to manage.
    """
    isolation_mode: Literal["database", "label"] = "label"
    tenants: List[Tenant] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.isolation_mode not in ("database", "label"):
            raise ValueError(
                f"Invalid isolation_mode '{self.isolation_mode}'.  Must be 'database' or 'label'.",
            )
        # Validate uniqueness of tenant ids.
        ids = [t.id for t in self.tenants]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate tenant ids detected.")
