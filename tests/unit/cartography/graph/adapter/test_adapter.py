"""
Unit tests for the graph database adapter abstraction layer.

All tests are mock-based and do not require a running database.
"""
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from cartography.graph.adapter.base import GraphAdapter
from cartography.graph.adapter.factory import create_adapter
from cartography.graph.adapter.memgraph_adapter import MemgraphAdapter
from cartography.graph.adapter.neo4j_adapter import Neo4jAdapter


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class TestGraphAdapterABC:
    """GraphAdapter cannot be instantiated directly."""

    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            GraphAdapter()  # type: ignore[abstract]

    def test_incomplete_subclass_cannot_instantiate(self):
        class PartialAdapter(GraphAdapter):
            def execute_query(self, query, params=None):
                ...

        with pytest.raises(TypeError):
            PartialAdapter()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class TestFactory:
    """create_adapter returns the right adapter type."""

    @patch("cartography.graph.adapter.neo4j_adapter.neo4j.GraphDatabase.driver")
    def test_creates_neo4j_adapter(self, mock_driver_cls):
        adapter = create_adapter(
            backend="neo4j",
            uri="bolt://localhost:7687",
            auth=("neo4j", "test"),
        )
        assert isinstance(adapter, Neo4jAdapter)
        mock_driver_cls.assert_called_once_with(
            "bolt://localhost:7687",
            auth=("neo4j", "test"),
        )

    @patch("cartography.graph.adapter.memgraph_adapter.neo4j.GraphDatabase.driver")
    def test_creates_memgraph_adapter(self, mock_driver_cls):
        adapter = create_adapter(
            backend="memgraph",
            uri="bolt://localhost:7687",
            auth=("memgraph", "pass"),
        )
        assert isinstance(adapter, MemgraphAdapter)
        mock_driver_cls.assert_called_once_with(
            "bolt://localhost:7687",
            auth=("memgraph", "pass"),
            encrypted=False,
        )

    def test_unknown_backend_raises(self):
        with pytest.raises(ValueError, match="Unknown graph backend"):
            create_adapter(backend="orientdb")

    @patch("cartography.graph.adapter.neo4j_adapter.neo4j.GraphDatabase.driver")
    def test_default_backend_is_neo4j(self, mock_driver_cls):
        adapter = create_adapter(uri="bolt://localhost:7687")
        assert isinstance(adapter, Neo4jAdapter)


# ---------------------------------------------------------------------------
# Neo4jAdapter
# ---------------------------------------------------------------------------


class TestNeo4jAdapter:
    """Neo4jAdapter delegates to the neo4j driver."""

    @patch("cartography.graph.adapter.neo4j_adapter.neo4j.GraphDatabase.driver")
    def _make_adapter(self, mock_driver_cls):
        mock_driver = MagicMock()
        mock_driver_cls.return_value = mock_driver
        adapter = Neo4jAdapter(uri="bolt://localhost:7687", auth=("neo4j", "pw"))
        return adapter, mock_driver, mock_driver_cls

    def test_driver_created_on_init(self):
        adapter, mock_driver, mock_driver_cls = self._make_adapter()
        mock_driver_cls.assert_called_once_with(
            "bolt://localhost:7687",
            auth=("neo4j", "pw"),
        )

    def test_execute_query_delegates_to_session_run(self):
        adapter, mock_driver, _ = self._make_adapter()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(
            return_value=mock_session,
        )
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        mock_record = MagicMock()
        mock_record.data.return_value = {"n": 1}
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([mock_record]))
        mock_session.run.return_value = mock_result

        records = adapter.execute_query("RETURN 1 AS n", {"x": 2})

        mock_session.run.assert_called_once_with("RETURN 1 AS n", {"x": 2})
        mock_result.consume.assert_called_once()
        assert records == [{"n": 1}]

    def test_execute_read_uses_read_transaction(self):
        adapter, mock_driver, _ = self._make_adapter()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(
            return_value=mock_session,
        )
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.execute_read.return_value = [{"count": 42}]

        result = adapter.execute_read("MATCH (n) RETURN count(n) AS count")

        mock_session.execute_read.assert_called_once()

    def test_session_context_manager(self):
        adapter, mock_driver, _ = self._make_adapter()
        mock_session = MagicMock()
        mock_driver.session.return_value = mock_session

        with adapter.session() as sess:
            assert sess is mock_session

        mock_session.close.assert_called_once()

    def test_verify_connectivity_success(self):
        adapter, mock_driver, _ = self._make_adapter()
        mock_driver.verify_connectivity.return_value = None

        assert adapter.verify_connectivity() is True
        mock_driver.verify_connectivity.assert_called_once()

    def test_verify_connectivity_failure(self):
        adapter, mock_driver, _ = self._make_adapter()
        mock_driver.verify_connectivity.side_effect = Exception("unreachable")

        assert adapter.verify_connectivity() is False

    def test_close_delegates_to_driver(self):
        adapter, mock_driver, _ = self._make_adapter()
        adapter.close()
        mock_driver.close.assert_called_once()

    def test_driver_property_exposes_underlying_driver(self):
        adapter, mock_driver, _ = self._make_adapter()
        assert adapter.driver is mock_driver


# ---------------------------------------------------------------------------
# MemgraphAdapter
# ---------------------------------------------------------------------------


class TestMemgraphAdapter:
    """MemgraphAdapter applies Memgraph-specific defaults."""

    @patch("cartography.graph.adapter.memgraph_adapter.neo4j.GraphDatabase.driver")
    def test_default_encrypted_false(self, mock_driver_cls):
        MemgraphAdapter(uri="bolt://localhost:7687")
        mock_driver_cls.assert_called_once_with(
            "bolt://localhost:7687",
            auth=None,
            encrypted=False,
        )

    @patch("cartography.graph.adapter.memgraph_adapter.neo4j.GraphDatabase.driver")
    def test_caller_can_override_encrypted(self, mock_driver_cls):
        MemgraphAdapter(uri="bolt://localhost:7687", encrypted=True)
        mock_driver_cls.assert_called_once_with(
            "bolt://localhost:7687",
            auth=None,
            encrypted=True,
        )

    @patch("cartography.graph.adapter.memgraph_adapter.neo4j.GraphDatabase.driver")
    def test_session_context_manager(self, mock_driver_cls):
        mock_driver = MagicMock()
        mock_driver_cls.return_value = mock_driver
        mock_session = MagicMock()
        mock_driver.session.return_value = mock_session

        adapter = MemgraphAdapter(uri="bolt://localhost:7687")
        with adapter.session() as sess:
            assert sess is mock_session

        mock_session.close.assert_called_once()

    @patch("cartography.graph.adapter.memgraph_adapter.neo4j.GraphDatabase.driver")
    def test_verify_connectivity_delegates(self, mock_driver_cls):
        mock_driver = MagicMock()
        mock_driver_cls.return_value = mock_driver

        adapter = MemgraphAdapter(uri="bolt://localhost:7687")
        assert adapter.verify_connectivity() is True
        mock_driver.verify_connectivity.assert_called_once()

    @patch("cartography.graph.adapter.memgraph_adapter.neo4j.GraphDatabase.driver")
    def test_close_delegates(self, mock_driver_cls):
        mock_driver = MagicMock()
        mock_driver_cls.return_value = mock_driver

        adapter = MemgraphAdapter(uri="bolt://localhost:7687")
        adapter.close()
        mock_driver.close.assert_called_once()
