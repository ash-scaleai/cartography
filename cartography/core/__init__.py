"""
cartography-core: Shared interface for Cartography standalone packages.

This module defines the public API that ``cartography-core`` would export
when the Cartography mono-repo is split into independent packages.  Today it
re-exports symbols from their current locations so that existing imports keep
working; standalone packages (``cartography-driftdetect``,
``cartography-rules``) would depend *only* on ``cartography-core``.

Exported categories
-------------------
* **Graph client** -- ``GraphClient`` (thin Neo4j wrapper)
* **Transaction helpers** -- ``read_list_of_dicts_tx``, ``read_single_value_tx``, etc.
* **Common exceptions** -- ``CartographyError``, ``GraphClientError``
* **Common types** -- re-exported for convenience
"""

from cartography.core.graph_client import CartographyError
from cartography.core.graph_client import GraphClient
from cartography.core.graph_client import GraphClientError

# Transaction helpers -- the most commonly used functions across packages.
from cartography.client.core.tx import read_list_of_dicts_tx
from cartography.client.core.tx import read_list_of_values_tx
from cartography.client.core.tx import read_single_dict_tx
from cartography.client.core.tx import read_single_value_tx

__all__ = [
    # Graph client
    "GraphClient",
    # Exceptions
    "CartographyError",
    "GraphClientError",
    # Transaction helpers
    "read_list_of_dicts_tx",
    "read_list_of_values_tx",
    "read_single_dict_tx",
    "read_single_value_tx",
]
