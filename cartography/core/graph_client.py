"""
Thin wrapper around the Neo4j Python driver.

``GraphClient`` provides a uniform interface for opening sessions and
executing read/write transactions against Neo4j.  Both
``cartography-driftdetect`` and ``cartography-rules`` need exactly this
capability; by centralising it in ``cartography-core`` we avoid duplicating
driver-management logic and make the dependency boundary explicit.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import neo4j
import neo4j.exceptions
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class CartographyError(Exception):
    """Base exception for all Cartography errors."""


class GraphClientError(CartographyError):
    """Raised when a graph-database operation fails."""


# ---------------------------------------------------------------------------
# GraphClient
# ---------------------------------------------------------------------------

class GraphClient:
    """Thin wrapper around a Neo4j driver.

    Parameters
    ----------
    uri : str
        Neo4j connection URI, e.g. ``bolt://localhost:7687``.
    user : str or None
        Neo4j username.  Pass *None* when authentication is disabled.
    password : str or None
        Neo4j password.  Pass *None* when authentication is disabled.
    database : str
        Neo4j database name.  Defaults to ``"neo4j"``.

    Examples
    --------
    >>> client = GraphClient("bolt://localhost:7687", "neo4j", "s3cret")
    >>> with client.session() as session:
    ...     results = session.execute_read(read_list_of_dicts_tx, query)
    >>> client.close()
    """

    def __init__(
        self,
        uri: str,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: str = "neo4j",
    ) -> None:
        self._uri = uri
        self._database = database
        auth = (user, password) if user or password else None
        try:
            self._driver: neo4j.Driver = GraphDatabase.driver(uri, auth=auth)
        except neo4j.exceptions.ServiceUnavailable as exc:
            raise GraphClientError(
                f"Unable to connect to Neo4j at '{uri}': {exc}"
            ) from exc
        except neo4j.exceptions.AuthError as exc:
            raise GraphClientError(
                f"Neo4j authentication failed for '{uri}': {exc}"
            ) from exc

    # -- context-manager support -------------------------------------------

    def __enter__(self) -> "GraphClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # -- public API --------------------------------------------------------

    @property
    def uri(self) -> str:
        """Return the Neo4j URI this client connects to."""
        return self._uri

    @property
    def database(self) -> str:
        """Return the Neo4j database name."""
        return self._database

    @property
    def driver(self) -> neo4j.Driver:
        """Return the underlying Neo4j driver instance."""
        return self._driver

    def session(self, **kwargs) -> neo4j.Session:
        """Open a new Neo4j session.

        Keyword arguments are forwarded to ``neo4j.Driver.session()``.
        If *database* is not specified it defaults to the value given at
        construction time.
        """
        kwargs.setdefault("database", self._database)
        return self._driver.session(**kwargs)

    def verify_connectivity(self) -> None:
        """Verify that the Neo4j server is reachable.

        Raises
        ------
        GraphClientError
            If the server cannot be reached.
        """
        try:
            self._driver.verify_connectivity()
        except Exception as exc:
            raise GraphClientError(
                f"Cannot reach Neo4j at '{self._uri}': {exc}"
            ) from exc

    def read_list_of_dicts(
        self, query: str, **kwargs
    ) -> List[Dict[str, Any]]:
        """Execute a read query and return a list of dicts.

        This is a convenience wrapper so callers do not need to import
        ``read_list_of_dicts_tx`` separately.
        """
        from cartography.client.core.tx import read_list_of_dicts_tx

        with self.session() as session:
            return session.execute_read(read_list_of_dicts_tx, query, **kwargs)

    def close(self) -> None:
        """Close the underlying driver and release all resources."""
        self._driver.close()

    def __repr__(self) -> str:
        return f"GraphClient(uri={self._uri!r}, database={self._database!r})"
