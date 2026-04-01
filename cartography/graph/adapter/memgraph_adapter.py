"""
Memgraph implementation of the GraphAdapter interface.

Memgraph speaks the Bolt protocol and is largely Cypher-compatible, so this
adapter reuses the ``neo4j`` Python driver with Memgraph-specific connection
defaults.

Key differences from Neo4j:
- ``encrypted=False`` by default (Memgraph's default listener is unencrypted).
- Index creation syntax may differ; helpers can be overridden as needed.
"""
import logging
from contextlib import contextmanager
from typing import Any
from typing import Dict
from typing import Iterator
from typing import List
from typing import Optional
from typing import Tuple

import neo4j

from cartography.graph.adapter.base import GraphAdapter

logger = logging.getLogger(__name__)

# Memgraph defaults that differ from Neo4j
_MEMGRAPH_DEFAULTS: Dict[str, Any] = {
    "encrypted": False,
}


class MemgraphAdapter(GraphAdapter):
    """
    Graph adapter for Memgraph, using the ``neo4j`` Python driver over Bolt.

    :param uri: Bolt URI for the Memgraph instance
        (e.g. ``bolt://localhost:7687``).
    :param auth: A ``(username, password)`` tuple, or *None* for no auth.
    :param kwargs: Extra keyword arguments forwarded to
        ``neo4j.GraphDatabase.driver``.  Memgraph-specific defaults
        (e.g. ``encrypted=False``) are applied first and can be overridden.
    """

    def __init__(
        self,
        uri: str,
        auth: Optional[Tuple[str, str]] = None,
        **kwargs: Any,
    ) -> None:
        self._uri = uri
        self._auth = auth
        # Merge Memgraph defaults with caller overrides
        driver_kwargs: Dict[str, Any] = {**_MEMGRAPH_DEFAULTS, **kwargs}
        self._driver_kwargs = driver_kwargs
        self._driver: neo4j.Driver = neo4j.GraphDatabase.driver(
            uri,
            auth=auth,
            **driver_kwargs,
        )

    # -- GraphAdapter interface ------------------------------------------------

    def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        params = params or {}
        with self._driver.session() as session:
            result = session.run(query, params)
            records = [record.data() for record in result]
            result.consume()
            return records

    def execute_read(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        params = params or {}
        with self._driver.session() as session:
            # Memgraph does not distinguish read/write transactions at the
            # protocol level, but we still use execute_read for consistency.
            def _read_tx(tx: neo4j.Transaction) -> List[Dict[str, Any]]:
                result = tx.run(query, params)
                records = [record.data() for record in result]
                result.consume()
                return records

            return session.execute_read(_read_tx)

    @contextmanager
    def session(self) -> Iterator[neo4j.Session]:
        session = self._driver.session()
        try:
            yield session
        finally:
            session.close()

    def verify_connectivity(self) -> bool:
        try:
            self._driver.verify_connectivity()
            return True
        except Exception:
            logger.exception("Memgraph connectivity check failed")
            return False

    def close(self) -> None:
        self._driver.close()

    # -- Convenience -----------------------------------------------------------

    @property
    def driver(self) -> neo4j.Driver:
        """Return the underlying ``neo4j.Driver`` for advanced use cases."""
        return self._driver
