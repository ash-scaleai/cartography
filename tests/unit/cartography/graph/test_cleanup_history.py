import json
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from cartography.graph.cleanup_history import RecordCountHistory


def _make_neo4j_session(stored_counts=None):
    """Create a mock Neo4j session that simulates CleanupHistory node storage."""
    storage = {"counts": json.dumps(stored_counts) if stored_counts else None}

    def run_side_effect(query, **kwargs):
        result = MagicMock()
        if "RETURN" in query:
            record = MagicMock()
            record.__getitem__ = lambda self, key: storage["counts"]
            result.single.return_value = (
                record if storage["counts"] is not None else None
            )
        elif "SET" in query:
            storage["counts"] = kwargs.get("counts_json", storage["counts"])
            result.single.return_value = None
        return result

    session = MagicMock()
    session.run.side_effect = run_side_effect
    return session


class TestRecordCountHistory:
    def test_get_history_empty(self):
        session = _make_neo4j_session(stored_counts=None)
        history = RecordCountHistory()
        assert history.get_history(session, "test_module") == []

    def test_add_and_get_history(self):
        session = _make_neo4j_session(stored_counts=None)
        history = RecordCountHistory()

        history.add_count(session, "test_module", 100)
        result = history.get_history(session, "test_module")
        assert result == [100]

    def test_add_multiple_counts(self):
        session = _make_neo4j_session(stored_counts=[50, 60])
        history = RecordCountHistory()

        history.add_count(session, "test_module", 70)
        result = history.get_history(session, "test_module")
        assert result == [50, 60, 70]

    def test_history_trimmed_to_size(self):
        # Start with 10 counts already stored
        existing = list(range(1, 11))  # [1, 2, ..., 10]
        session = _make_neo4j_session(stored_counts=existing)
        history = RecordCountHistory(history_size=10)

        history.add_count(session, "test_module", 11)
        result = history.get_history(session, "test_module")
        # Should have dropped the first entry (1) and kept [2..11]
        assert result == list(range(2, 12))
        assert len(result) == 10

    def test_custom_history_size(self):
        existing = [10, 20, 30, 40, 50]
        session = _make_neo4j_session(stored_counts=existing)
        history = RecordCountHistory(history_size=3)

        history.add_count(session, "test_module", 60)
        result = history.get_history(session, "test_module")
        assert result == [40, 50, 60]

    def test_rolling_average_empty(self):
        session = _make_neo4j_session(stored_counts=None)
        history = RecordCountHistory()
        assert history.get_rolling_average(session, "test_module") == 0.0

    def test_rolling_average(self):
        session = _make_neo4j_session(stored_counts=[100, 200, 300])
        history = RecordCountHistory()
        assert history.get_rolling_average(session, "test_module") == 200.0

    def test_rolling_average_single_value(self):
        session = _make_neo4j_session(stored_counts=[42])
        history = RecordCountHistory()
        assert history.get_rolling_average(session, "test_module") == 42.0

    def test_standard_deviation_empty(self):
        session = _make_neo4j_session(stored_counts=None)
        history = RecordCountHistory()
        assert history.get_standard_deviation(session, "test_module") == 0.0

    def test_standard_deviation_single_value(self):
        session = _make_neo4j_session(stored_counts=[42])
        history = RecordCountHistory()
        # < 2 data points => 0.0
        assert history.get_standard_deviation(session, "test_module") == 0.0

    def test_standard_deviation_all_same(self):
        session = _make_neo4j_session(stored_counts=[100, 100, 100, 100])
        history = RecordCountHistory()
        assert history.get_standard_deviation(session, "test_module") == 0.0

    def test_standard_deviation_known_values(self):
        # [10, 20, 30] -> mean=20, variance=((100+0+100)/3)=66.67, std=8.165
        session = _make_neo4j_session(stored_counts=[10, 20, 30])
        history = RecordCountHistory()
        std_dev = history.get_standard_deviation(session, "test_module")
        assert abs(std_dev - 8.165) < 0.01
