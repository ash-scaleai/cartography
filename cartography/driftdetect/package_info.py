"""
Package metadata for ``cartography-driftdetect``.

This module captures everything needed to publish ``cartography-driftdetect``
as an independent package.  It is *not* used at runtime today -- it exists to
document the dependency boundary so that a future split is straightforward.

Dependency analysis
-------------------
The driftdetect package imports from the main cartography tree in exactly one
place:

* ``cartography.client.core.tx.read_list_of_dicts_tx``
  (used by ``get_states.py`` to execute Neo4j read transactions)

When split, that import would become:

* ``cartography.core.read_list_of_dicts_tx``   (from ``cartography-core``)

All other imports are either stdlib, third-party (``neo4j``, ``marshmallow``),
or intra-package (``cartography.driftdetect.*``).
"""

PACKAGE_NAME = "cartography-driftdetect"
VERSION = "0.1.0"
DESCRIPTION = (
    "Drift detection for Cartography: compare point-in-time snapshots of "
    "your Neo4j graph to surface unexpected changes."
)

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

# The ``cartography-core`` package provides the Neo4j graph client and
# transaction helpers that driftdetect needs to query the graph.
CORE_DEPENDENCY = "cartography-core>=0.1.0"

# Third-party runtime dependencies (versions match the monorepo pyproject.toml).
THIRD_PARTY_DEPENDENCIES = [
    "neo4j>=6.0.0",
    "marshmallow>=3.0.0rc7",
]

# Combined install_requires for a standalone pyproject.toml.
INSTALL_REQUIRES = [CORE_DEPENDENCY] + THIRD_PARTY_DEPENDENCIES

# ---------------------------------------------------------------------------
# Imports that would move to cartography-core
# ---------------------------------------------------------------------------
#
# When driftdetect is extracted, the following import:
#
#     from cartography.client.core.tx import read_list_of_dicts_tx
#
# becomes:
#
#     from cartography.core import read_list_of_dicts_tx
#
CARTOGRAPHY_CORE_IMPORTS = [
    "cartography.client.core.tx.read_list_of_dicts_tx",
]

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

ENTRY_POINTS = {
    "console_scripts": [
        "cartography-detectdrift = cartography.driftdetect.cli:main",
    ],
}
