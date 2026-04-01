"""
Package metadata for ``cartography-rules``.

This module captures everything needed to publish ``cartography-rules``
as an independent package.  It is *not* used at runtime today -- it exists to
document the dependency boundary so that a future split is straightforward.

Dependency analysis
-------------------
The rules package imports from the main cartography tree in exactly one place:

* ``cartography.client.core.tx.read_list_of_dicts_tx``
  (used by ``runners.py`` to execute Neo4j read transactions)

When split, that import would become:

* ``cartography.core.read_list_of_dicts_tx``   (from ``cartography-core``)

All other imports are either stdlib, third-party (``neo4j``, ``typer``,
``pydantic``), or intra-package (``cartography.rules.*``).
"""

PACKAGE_NAME = "cartography-rules"
VERSION = "0.1.0"
DESCRIPTION = (
    "Security rules engine for Cartography: execute compliance frameworks "
    "against your Neo4j graph and present findings."
)

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

CORE_DEPENDENCY = "cartography-core>=0.1.0"

THIRD_PARTY_DEPENDENCIES = [
    "neo4j>=6.0.0",
    "typer>=0.9.0",
    "pydantic>=2.0.0",
    "typing_extensions",
]

INSTALL_REQUIRES = [CORE_DEPENDENCY] + THIRD_PARTY_DEPENDENCIES

# ---------------------------------------------------------------------------
# Imports that would move to cartography-core
# ---------------------------------------------------------------------------

CARTOGRAPHY_CORE_IMPORTS = [
    "cartography.client.core.tx.read_list_of_dicts_tx",
    # Used by cis_aws_iam rule definitions for date arithmetic:
    "cartography.util.to_datetime",
]

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

ENTRY_POINTS = {
    "console_scripts": [
        "cartography-rules = cartography.rules.cli:main",
    ],
}
