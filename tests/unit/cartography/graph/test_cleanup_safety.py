import json
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from cartography.graph.cleanup_safety import CleanupSafety


def _make_combined_session(history_counts=None, circuit_failures=None):
    """
    Create a mock Neo4j session that simulates both CleanupHistory
    and CircuitBreakerState node storage.
    """
    history_storage = {
        "counts": json.dumps(history_counts) if history_counts else None,
    }
    cb_storage = {"failures": circuit_failures}

    def run_side_effect(query, **kwargs):
        result = MagicMock()

        if "CleanupHistory" in query:
            if "RETURN" in query:
                record = MagicMock()
                record.__getitem__ = lambda self, key: history_storage["counts"]
                result.single.return_value = (
                    record if history_storage["counts"] is not None else None
                )
            elif "SET" in query:
                history_storage["counts"] = kwargs.get(
                    "counts_json", history_storage["counts"],
                )
        elif "CircuitBreakerState" in query:
            if "RETURN" in query:
                if cb_storage["failures"] is not None:
                    record = MagicMock()
                    record.__getitem__ = lambda self, key: cb_storage["failures"]
                    result.single.return_value = record
                else:
                    result.single.return_value = None
            elif "ON CREATE SET" in query:
                if cb_storage["failures"] is None:
                    cb_storage["failures"] = 1
                else:
                    cb_storage["failures"] += 1
            elif "consecutive_failures = 0" in query:
                cb_storage["failures"] = 0
        return result

    session = MagicMock()
    session.run.side_effect = run_side_effect
    return session


class TestCleanupSafety:
    def test_safe_when_no_issues(self):
        session = _make_combined_session(
            history_counts=[100, 100, 100, 100, 100],
            circuit_failures=0,
        )
        safety = CleanupSafety()
        is_safe, reason = safety.check_cleanup_safe(
            session, "test_module", 100, previous_count=105,
        )
        assert is_safe is True
        assert reason == ""

    def test_blocked_by_circuit_breaker(self):
        session = _make_combined_session(
            history_counts=[100, 100, 100],
            circuit_failures=3,
        )
        safety = CleanupSafety()
        is_safe, reason = safety.check_cleanup_safe(
            session, "test_module", 100,
        )
        assert is_safe is False
        assert "Circuit breaker" in reason

    def test_blocked_by_threshold(self):
        session = _make_combined_session(
            history_counts=[100, 100, 100],
            circuit_failures=0,
        )
        safety = CleanupSafety(cleanup_threshold=0.5)
        # previous=100, current=10 -> removal fraction = 0.9 > 0.5
        is_safe, reason = safety.check_cleanup_safe(
            session, "test_module", 10, previous_count=100,
        )
        assert is_safe is False
        assert "90.0%" in reason

    def test_threshold_skipped_when_no_previous(self):
        session = _make_combined_session(
            history_counts=[100, 100, 100],
            circuit_failures=0,
        )
        safety = CleanupSafety(cleanup_threshold=0.5)
        is_safe, reason = safety.check_cleanup_safe(
            session, "test_module", 100,
        )
        assert is_safe is True

    def test_blocked_by_anomaly(self):
        # History all around 100, current count is 500 -> anomalous
        session = _make_combined_session(
            history_counts=[100, 100, 100, 102, 98, 101, 99, 100, 100, 100],
            circuit_failures=0,
        )
        safety = CleanupSafety()
        is_safe, reason = safety.check_cleanup_safe(
            session, "test_module", 500,
        )
        assert is_safe is False
        assert "Anomaly" in reason

    def test_anomaly_not_triggered_with_insufficient_history(self):
        session = _make_combined_session(
            history_counts=[100],
            circuit_failures=0,
        )
        safety = CleanupSafety()
        is_safe, reason = safety.check_cleanup_safe(
            session, "test_module", 500,
        )
        assert is_safe is True

    def test_record_count(self):
        session = _make_combined_session(
            history_counts=[100, 200],
            circuit_failures=0,
        )
        safety = CleanupSafety()
        safety.record_count(session, "test_module", 300)
        history = safety.history.get_history(session, "test_module")
        assert history == [100, 200, 300]

    def test_record_sync_success(self):
        session = _make_combined_session(
            history_counts=None,
            circuit_failures=3,
        )
        safety = CleanupSafety()
        assert safety.circuit_breaker.is_open(session, "test_module") is True

        safety.record_sync_success(session, "test_module")
        assert safety.circuit_breaker.is_open(session, "test_module") is False

    def test_record_sync_failure(self):
        session = _make_combined_session(
            history_counts=None,
            circuit_failures=None,
        )
        safety = CleanupSafety()
        safety.record_sync_failure(session, "test_module")
        assert (
            safety.circuit_breaker.get_failure_count(session, "test_module") == 1
        )

    def test_get_anomaly_alert_none(self):
        session = _make_combined_session(
            history_counts=[100, 100, 100, 100, 100],
            circuit_failures=0,
        )
        safety = CleanupSafety()
        alert = safety.get_anomaly_alert(session, "test_module", 100)
        assert alert is None

    def test_get_anomaly_alert_triggered(self):
        session = _make_combined_session(
            history_counts=[100, 100, 100, 102, 98, 101, 99, 100, 100, 100],
            circuit_failures=0,
        )
        safety = CleanupSafety()
        alert = safety.get_anomaly_alert(session, "test_module", 500)
        assert alert is not None
        assert alert.module_name == "test_module"
        assert alert.current_count == 500

    def test_first_run_no_history(self):
        """First run with no history should be safe."""
        session = _make_combined_session(
            history_counts=None,
            circuit_failures=None,
        )
        safety = CleanupSafety()
        is_safe, reason = safety.check_cleanup_safe(
            session, "new_module", 100,
        )
        assert is_safe is True
        assert reason == ""

    def test_all_same_counts_normal(self):
        """When all historical counts are identical, same count is normal."""
        session = _make_combined_session(
            history_counts=[50, 50, 50, 50, 50],
            circuit_failures=0,
        )
        safety = CleanupSafety()
        is_safe, reason = safety.check_cleanup_safe(
            session, "test_module", 50,
        )
        assert is_safe is True

    def test_all_same_counts_different_value_anomalous(self):
        """When all historical counts are identical, any different value is anomalous."""
        session = _make_combined_session(
            history_counts=[50, 50, 50, 50, 50],
            circuit_failures=0,
        )
        safety = CleanupSafety()
        is_safe, reason = safety.check_cleanup_safe(
            session, "test_module", 51,
        )
        assert is_safe is False
        assert "Anomaly" in reason

    def test_configurable_parameters(self):
        """Verify that config parameters are properly passed through."""
        safety = CleanupSafety(
            history_size=5,
            anomaly_std_devs=3.0,
            circuit_breaker_threshold=5,
            cleanup_threshold=0.8,
        )
        assert safety.history.history_size == 5
        assert safety.anomaly_std_devs == 3.0
        assert safety.circuit_breaker.threshold == 5
        assert safety.cleanup_threshold == 0.8
