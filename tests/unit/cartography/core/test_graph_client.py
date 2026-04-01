"""
Tests for cartography.core.graph_client.

Verifies that GraphClient provides the interface both driftdetect and rules
need: session management, read helpers, and proper error handling.
"""

from unittest.mock import MagicMock, patch

import pytest

from cartography.core.graph_client import CartographyError, GraphClient, GraphClientError


class TestGraphClientError:
    """GraphClientError inherits from CartographyError."""

    def test_hierarchy(self):
        assert issubclass(GraphClientError, CartographyError)
        assert issubclass(GraphClientError, Exception)

    def test_can_raise_and_catch(self):
        with pytest.raises(CartographyError):
            raise GraphClientError("boom")


class TestGraphClientInit:
    """Construction and authentication."""

    @patch("cartography.core.graph_client.GraphDatabase")
    def test_creates_driver_with_auth(self, mock_gdb):
        mock_gdb.driver.return_value = MagicMock()
        client = GraphClient("bolt://localhost:7687", user="neo4j", password="pass")
        mock_gdb.driver.assert_called_once_with(
            "bolt://localhost:7687", auth=("neo4j", "pass"),
        )
        assert client.uri == "bolt://localhost:7687"
        assert client.database == "neo4j"
        client.close()

    @patch("cartography.core.graph_client.GraphDatabase")
    def test_creates_driver_without_auth(self, mock_gdb):
        mock_gdb.driver.return_value = MagicMock()
        client = GraphClient("bolt://localhost:7687")
        mock_gdb.driver.assert_called_once_with("bolt://localhost:7687", auth=None)
        client.close()

    @patch("cartography.core.graph_client.GraphDatabase")
    def test_custom_database(self, mock_gdb):
        mock_gdb.driver.return_value = MagicMock()
        client = GraphClient("bolt://localhost:7687", database="mydb")
        assert client.database == "mydb"
        client.close()

    @patch("cartography.core.graph_client.GraphDatabase")
    def test_service_unavailable_raises_graph_client_error(self, mock_gdb):
        import neo4j.exceptions
        mock_gdb.driver.side_effect = neo4j.exceptions.ServiceUnavailable("down")
        with pytest.raises(GraphClientError, match="Unable to connect"):
            GraphClient("bolt://localhost:7687")

    @patch("cartography.core.graph_client.GraphDatabase")
    def test_auth_error_raises_graph_client_error(self, mock_gdb):
        import neo4j.exceptions
        mock_gdb.driver.side_effect = neo4j.exceptions.AuthError("bad creds")
        with pytest.raises(GraphClientError, match="authentication failed"):
            GraphClient("bolt://localhost:7687", user="neo4j", password="wrong")


class TestGraphClientSession:
    """Session and driver access."""

    @patch("cartography.core.graph_client.GraphDatabase")
    def test_session_uses_default_database(self, mock_gdb):
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver
        client = GraphClient("bolt://localhost:7687", database="testdb")
        client.session()
        mock_driver.session.assert_called_once_with(database="testdb")
        client.close()

    @patch("cartography.core.graph_client.GraphDatabase")
    def test_driver_property(self, mock_gdb):
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver
        client = GraphClient("bolt://localhost:7687")
        assert client.driver is mock_driver
        client.close()


class TestGraphClientContextManager:
    """Context-manager protocol."""

    @patch("cartography.core.graph_client.GraphDatabase")
    def test_context_manager_closes_driver(self, mock_gdb):
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver
        with GraphClient("bolt://localhost:7687") as client:
            assert client.uri == "bolt://localhost:7687"
        mock_driver.close.assert_called_once()


class TestGraphClientVerifyConnectivity:
    """verify_connectivity wraps driver errors."""

    @patch("cartography.core.graph_client.GraphDatabase")
    def test_verify_connectivity_success(self, mock_gdb):
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver
        client = GraphClient("bolt://localhost:7687")
        client.verify_connectivity()
        mock_driver.verify_connectivity.assert_called_once()
        client.close()

    @patch("cartography.core.graph_client.GraphDatabase")
    def test_verify_connectivity_failure(self, mock_gdb):
        mock_driver = MagicMock()
        mock_driver.verify_connectivity.side_effect = Exception("unreachable")
        mock_gdb.driver.return_value = mock_driver
        client = GraphClient("bolt://localhost:7687")
        with pytest.raises(GraphClientError, match="Cannot reach Neo4j"):
            client.verify_connectivity()
        client.close()


class TestGraphClientReadListOfDicts:
    """Convenience read method."""

    @patch("cartography.core.graph_client.GraphDatabase")
    def test_read_list_of_dicts(self, mock_gdb):
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.execute_read.return_value = [{"a": 1}]
        mock_driver.session.return_value = mock_session
        mock_gdb.driver.return_value = mock_driver

        client = GraphClient("bolt://localhost:7687")
        result = client.read_list_of_dicts("MATCH (n) RETURN n")
        assert result == [{"a": 1}]
        client.close()


class TestGraphClientRepr:
    """String representation."""

    @patch("cartography.core.graph_client.GraphDatabase")
    def test_repr(self, mock_gdb):
        mock_gdb.driver.return_value = MagicMock()
        client = GraphClient("bolt://localhost:7687", database="testdb")
        assert "bolt://localhost:7687" in repr(client)
        assert "testdb" in repr(client)
        client.close()
