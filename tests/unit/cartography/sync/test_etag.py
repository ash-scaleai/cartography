from unittest.mock import MagicMock

from cartography.sync.etag import check_etag
from cartography.sync.etag import ETagStore


class TestETagStore:
    def _make_session(self, stored_rows=None):
        session = MagicMock()
        if stored_rows is None:
            stored_rows = []
        session.execute_read.return_value = stored_rows
        return session

    def test_get_etag_found(self):
        session = self._make_session([{"etag": "abc123"}])
        store = ETagStore(session)
        assert store.get_etag("https://api.example.com/resources") == "abc123"

    def test_get_etag_not_found(self):
        session = self._make_session([])
        store = ETagStore(session)
        assert store.get_etag("https://api.example.com/resources") is None

    def test_store_etag(self):
        session = self._make_session()
        store = ETagStore(session)
        # Should not raise
        store.store_etag("https://api.example.com/resources", "etag-value", lastupdated=1)

    def test_get_all_etags(self):
        rows = [
            {"endpoint": "https://api.example.com/a", "etag": "e1"},
            {"endpoint": "https://api.example.com/b", "etag": "e2"},
        ]
        session = self._make_session(rows)
        store = ETagStore(session)
        result = store.get_all_etags()
        assert result == {
            "https://api.example.com/a": "e1",
            "https://api.example.com/b": "e2",
        }


class TestCheckEtag:
    def test_no_stored_etag_returns_false(self):
        """First run — must fetch data."""
        assert check_etag("https://api.example.com/resources", None) is False

    def test_with_stored_etag_returns_false_stub(self):
        """Stub always returns False (data must be fetched)."""
        assert check_etag("https://api.example.com/resources", "abc") is False
