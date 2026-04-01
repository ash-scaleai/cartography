"""
Factory function for creating graph database adapters.

Usage::

    adapter = create_adapter(backend="neo4j", uri="bolt://localhost:7687",
                             auth=("neo4j", "password"))
"""
from typing import Any
from typing import Optional
from typing import Tuple

from cartography.graph.adapter.base import GraphAdapter


def create_adapter(
    backend: str = "neo4j",
    uri: str = "bolt://localhost:7687",
    auth: Optional[Tuple[str, str]] = None,
    **kwargs: Any,
) -> GraphAdapter:
    """
    Instantiate the appropriate :class:`GraphAdapter` for the requested backend.

    :param backend: One of ``"neo4j"`` (default) or ``"memgraph"``.
    :param uri: Bolt URI for the graph database.
    :param auth: Optional ``(username, password)`` tuple.
    :param kwargs: Extra keyword arguments forwarded to the adapter constructor.
    :return: A ready-to-use :class:`GraphAdapter` instance.
    :raises ValueError: If *backend* is not a recognised name.
    """
    backend_lower = backend.lower().strip()

    if backend_lower == "neo4j":
        from cartography.graph.adapter.neo4j_adapter import Neo4jAdapter
        return Neo4jAdapter(uri=uri, auth=auth, **kwargs)
    elif backend_lower == "memgraph":
        from cartography.graph.adapter.memgraph_adapter import MemgraphAdapter
        return MemgraphAdapter(uri=uri, auth=auth, **kwargs)
    else:
        raise ValueError(
            f"Unknown graph backend {backend!r}. "
            f"Supported backends: 'neo4j', 'memgraph'."
        )
