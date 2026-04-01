from unittest.mock import MagicMock
from unittest.mock import patch

from cartography.sync.checksum import compute_checksum
from cartography.sync.checksum import ChecksumStore
from cartography.sync.checksum import filter_unchanged
from cartography.sync.checksum import update_checksums


class TestComputeChecksum:
    def test_deterministic(self):
        """Same dict always produces the same hash."""
        record = {"id": "i-123", "name": "web-server", "type": "t2.micro"}
        assert compute_checksum(record) == compute_checksum(record)

    def test_changes_when_record_changes(self):
        """Modifying a value produces a different hash."""
        record_a = {"id": "i-123", "name": "web-server"}
        record_b = {"id": "i-123", "name": "api-server"}
        assert compute_checksum(record_a) != compute_checksum(record_b)

    def test_key_ordering_does_not_affect_checksum(self):
        """Dicts with the same keys in different insertion order hash equally."""
        record_a = {"id": "i-123", "name": "web-server", "type": "t2.micro"}
        record_b = {"type": "t2.micro", "id": "i-123", "name": "web-server"}
        assert compute_checksum(record_a) == compute_checksum(record_b)

    def test_empty_dict(self):
        """An empty dict produces a valid hash."""
        h = compute_checksum({})
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex digest length

    def test_nested_dict(self):
        """Nested structures are serialized deterministically."""
        record_a = {"id": "1", "tags": {"env": "prod", "team": "infra"}}
        record_b = {"tags": {"team": "infra", "env": "prod"}, "id": "1"}
        assert compute_checksum(record_a) == compute_checksum(record_b)

    def test_non_string_values(self):
        """Non-string values (int, bool, None) are handled."""
        record = {"id": 1, "active": True, "extra": None}
        h = compute_checksum(record)
        assert isinstance(h, str)
        assert len(h) == 64


class TestChecksumStore:
    def _make_session(self, stored_rows=None):
        """Build a mock neo4j session that returns *stored_rows* on read."""
        session = MagicMock()
        if stored_rows is None:
            stored_rows = []
        session.execute_read.return_value = stored_rows
        return session

    def test_get_checksums_returns_dict(self):
        rows = [
            {"resource_id": "i-1", "checksum": "aaa"},
            {"resource_id": "i-2", "checksum": "bbb"},
        ]
        session = self._make_session(rows)
        store = ChecksumStore(session)
        result = store.get_checksums("ec2:instance")
        assert result == {"i-1": "aaa", "i-2": "bbb"}

    def test_get_checksums_empty(self):
        session = self._make_session([])
        store = ChecksumStore(session)
        assert store.get_checksums("ec2:instance") == {}

    def test_update_checksums_calls_write(self):
        session = self._make_session()
        store = ChecksumStore(session)
        records = [{"id": "i-1", "name": "a"}, {"id": "i-2", "name": "b"}]
        with patch("cartography.sync.checksum.run_write_query") as mock_write:
            store.update_checksums(records, "ec2:instance", id_field="id", lastupdated=1)
            mock_write.assert_called_once()
            call_kwargs = mock_write.call_args
            assert call_kwargs[1]["module"] == "ec2:instance"

    def test_update_checksums_empty_records(self):
        session = self._make_session()
        store = ChecksumStore(session)
        with patch("cartography.sync.checksum.run_write_query") as mock_write:
            store.update_checksums([], "ec2:instance")
            mock_write.assert_not_called()


class TestFilterUnchanged:
    def _make_session(self, stored_rows=None):
        session = MagicMock()
        if stored_rows is None:
            stored_rows = []
        session.execute_read.return_value = stored_rows
        return session

    def test_first_run_passes_everything(self):
        """When no checksums exist all records are returned."""
        records = [{"id": "i-1", "name": "a"}, {"id": "i-2", "name": "b"}]
        session = self._make_session([])
        result = filter_unchanged(records, "ec2:instance", session, id_field="id")
        assert result == records

    def test_filters_unchanged_records(self):
        """Records whose checksum matches the stored value are excluded."""
        rec_a = {"id": "i-1", "name": "a"}
        rec_b = {"id": "i-2", "name": "b"}
        stored = [
            {"resource_id": "i-1", "checksum": compute_checksum(rec_a)},
            {"resource_id": "i-2", "checksum": "stale-checksum"},
        ]
        session = self._make_session(stored)
        result = filter_unchanged([rec_a, rec_b], "ec2:instance", session, id_field="id")
        # rec_a unchanged, rec_b changed
        assert len(result) == 1
        assert result[0]["id"] == "i-2"

    def test_all_unchanged(self):
        rec = {"id": "i-1", "name": "a"}
        stored = [{"resource_id": "i-1", "checksum": compute_checksum(rec)}]
        session = self._make_session(stored)
        result = filter_unchanged([rec], "ec2:instance", session, id_field="id")
        assert result == []

    def test_empty_records(self):
        session = self._make_session([])
        result = filter_unchanged([], "ec2:instance", session)
        assert result == []


class TestUpdateChecksums:
    def test_update_checksums_delegates(self):
        session = MagicMock()
        session.execute_read.return_value = []
        records = [{"id": "i-1", "val": "x"}]
        with patch("cartography.sync.checksum.run_write_query") as mock_write:
            update_checksums(records, "mod", session, id_field="id", lastupdated=42)
            mock_write.assert_called_once()
