import logging
from unittest.mock import MagicMock
from unittest.mock import patch

from cartography.sync.checksum import compute_checksum
from cartography.sync.differential import DifferentialSyncManager
from cartography.sync.differential import sync_with_diff


class TestDifferentialSyncManager:
    def _make_session(self, stored_rows=None):
        session = MagicMock()
        if stored_rows is None:
            stored_rows = []
        session.execute_read.return_value = stored_rows
        return session

    def test_first_run_loads_everything(self):
        """No stored checksums — all records are loaded."""
        session = self._make_session([])
        records = [{"id": "i-1", "v": "a"}, {"id": "i-2", "v": "b"}]
        load_func = MagicMock()

        with patch("cartography.sync.checksum.run_write_query"):
            dsm = DifferentialSyncManager(session, "ec2:instance", id_field="id")
            stats = dsm.sync_with_diff(records, load_func, lastupdated=1)

        assert stats["fetched"] == 2
        assert stats["changed"] == 2
        assert stats["skipped"] == 0
        load_func.assert_called_once_with(records)

    def test_skips_unchanged(self):
        """Records with matching checksums are not loaded."""
        rec_a = {"id": "i-1", "v": "a"}
        rec_b = {"id": "i-2", "v": "b"}
        stored = [
            {"resource_id": "i-1", "checksum": compute_checksum(rec_a)},
            {"resource_id": "i-2", "checksum": "old-checksum"},
        ]
        session = self._make_session(stored)
        load_func = MagicMock()

        with patch("cartography.sync.checksum.run_write_query"):
            dsm = DifferentialSyncManager(session, "ec2:instance", id_field="id")
            stats = dsm.sync_with_diff([rec_a, rec_b], load_func, lastupdated=2)

        assert stats["fetched"] == 2
        assert stats["changed"] == 1
        assert stats["skipped"] == 1
        # Only rec_b should be loaded
        load_func.assert_called_once()
        loaded = load_func.call_args[0][0]
        assert len(loaded) == 1
        assert loaded[0]["id"] == "i-2"

    def test_all_unchanged_skips_load(self):
        rec = {"id": "i-1", "v": "a"}
        stored = [{"resource_id": "i-1", "checksum": compute_checksum(rec)}]
        session = self._make_session(stored)
        load_func = MagicMock()

        with patch("cartography.sync.checksum.run_write_query"):
            dsm = DifferentialSyncManager(session, "ec2:instance", id_field="id")
            stats = dsm.sync_with_diff([rec], load_func, lastupdated=3)

        assert stats["fetched"] == 1
        assert stats["changed"] == 0
        assert stats["skipped"] == 1
        load_func.assert_not_called()

    def test_empty_records(self):
        session = self._make_session([])
        load_func = MagicMock()

        with patch("cartography.sync.checksum.run_write_query"):
            dsm = DifferentialSyncManager(session, "ec2:instance", id_field="id")
            stats = dsm.sync_with_diff([], load_func)

        assert stats == {"fetched": 0, "changed": 0, "skipped": 0}
        load_func.assert_not_called()

    def test_kwargs_forwarded_to_load_func(self):
        session = self._make_session([])
        records = [{"id": "i-1", "v": "a"}]
        load_func = MagicMock()

        with patch("cartography.sync.checksum.run_write_query"):
            dsm = DifferentialSyncManager(session, "mod", id_field="id")
            dsm.sync_with_diff(records, load_func, lastupdated=1, Region="us-east-1")

        load_func.assert_called_once_with(records, Region="us-east-1")

    def test_stats_logging(self, caplog):
        session = self._make_session([])
        records = [{"id": "i-1"}, {"id": "i-2"}, {"id": "i-3"}]
        load_func = MagicMock()

        with caplog.at_level(logging.INFO, logger="cartography.sync.differential"):
            with patch("cartography.sync.checksum.run_write_query"):
                dsm = DifferentialSyncManager(session, "test:mod", id_field="id")
                dsm.sync_with_diff(records, load_func)

        assert "test:mod" in caplog.text
        assert "3 records fetched" in caplog.text
        assert "3 changed" in caplog.text
        assert "0 skipped" in caplog.text

    def test_module_name_property(self):
        session = self._make_session([])
        dsm = DifferentialSyncManager(session, "ec2:instance")
        assert dsm.module_name == "ec2:instance"


class TestSyncWithDiffFunction:
    def test_delegates_to_manager(self):
        """The module-level convenience function produces the same result."""
        session = MagicMock()
        session.execute_read.return_value = []
        records = [{"id": "i-1", "v": "x"}]
        load_func = MagicMock()

        with patch("cartography.sync.checksum.run_write_query"):
            stats = sync_with_diff(
                records, "ec2:instance", session, load_func,
                id_field="id", lastupdated=5,
            )

        assert stats["fetched"] == 1
        assert stats["changed"] == 1
        load_func.assert_called_once()
