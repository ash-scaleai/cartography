"""
Abstract base class for graph database adapters.

This module defines the interface that all graph database backends must implement.
The adapter pattern allows cartography to support multiple graph databases
(Neo4j, Memgraph, etc.) without changing intel modules.
"""
from abc import ABC
from abc import abstractmethod
from contextlib import contextmanager
from typing import Any
from typing import Dict
from typing import Iterator
from typing import List
from typing import Optional


class GraphAdapter(ABC):
    """
    Abstract base class for graph database adapters.

    All graph database backends must implement this interface to be compatible
    with cartography's ingestion pipeline. The interface is designed to be a
    thin wrapper around the underlying driver, providing just enough abstraction
    to swap backends without modifying intel modules.
    """

    @abstractmethod
    def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute a write query against the graph database.

        :param query: The Cypher query string to execute.
        :param params: Optional dictionary of query parameters.
        :return: A list of result records as dictionaries.
        """
        ...

    @abstractmethod
    def execute_read(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute a read-only query against the graph database.

        :param query: The Cypher query string to execute.
        :param params: Optional dictionary of query parameters.
        :return: A list of result records as dictionaries.
        """
        ...

    @abstractmethod
    @contextmanager
    def session(self) -> Iterator[Any]:
        """
        Provide a session context manager compatible with the existing
        cartography pipeline. The yielded session object should be usable
        wherever ``neo4j.Session`` is used today.

        Usage::

            with adapter.session() as sess:
                sess.run("MATCH (n) RETURN n LIMIT 1")
        """
        ...

    @abstractmethod
    def verify_connectivity(self) -> bool:
        """
        Check that the graph database is reachable.

        :return: True if the database is reachable, False otherwise.
        """
        ...

    @abstractmethod
    def close(self) -> None:
        """
        Release all resources held by the adapter (driver connections, etc.).
        """
        ...
