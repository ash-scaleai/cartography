"""
Neo4j implementation of the GraphAdapter interface.

Wraps the official ``neo4j`` Python driver, delegating all operations to
``neo4j.GraphDatabase.driver``. This is the default backend for cartography.
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


class Neo4jAdapter(GraphAdapter):
    """
    Graph adapter backed by the official Neo4j Python driver.

    :param uri: Bolt URI for the Neo4j instance (e.g. ``bolt://localhost:7687``).
    :param auth: A ``(username, password)`` tuple, or *None* for no auth.
    :param kwargs: Extra keyword arguments forwarded to
        ``neo4j.GraphDatabase.driver``.
    """

    def __init__(
        self,
        uri: str,
        auth: Optional[Tuple[str, str]] = None,
        **kwargs: Any,
    ) -> None:
        self._uri = uri
        self._auth = auth
        self._driver_kwargs = kwargs
        self._driver: neo4j.Driver = neo4j.GraphDatabase.driver(
            uri,
            auth=auth,
            **kwargs,
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
            logger.exception("Neo4j connectivity check failed")
            return False

    def close(self) -> None:
        self._driver.close()

    # -- Convenience -----------------------------------------------------------

    @property
    def driver(self) -> neo4j.Driver:
        """Return the underlying ``neo4j.Driver`` for advanced use cases."""
        return self._driver
