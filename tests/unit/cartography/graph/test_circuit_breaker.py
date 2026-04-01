import json
from unittest.mock import MagicMock

import pytest

from cartography.graph.circuit_breaker import CircuitBreaker


def _make_neo4j_session(initial_failures=None):
    """Create a mock Neo4j session that simulates CircuitBreakerState node storage."""
    storage = {"failures": initial_failures}

    def run_side_effect(query, **kwargs):
        result = MagicMock()
        if "RETURN" in query:
            if storage["failures"] is not None:
                record = MagicMock()
                record.__getitem__ = lambda self, key: storage["failures"]
                result.single.return_value = record
            else:
                result.single.return_value = None
        elif "ON CREATE SET" in query:
            # MERGE with ON CREATE / ON MATCH
            if storage["failures"] is None:
                storage["failures"] = 1
            else:
                storage["failures"] += 1
        elif "consecutive_failures = 0" in query:
            storage["failures"] = 0
        return result

    session = MagicMock()
    session.run.side_effect = run_side_effect
    return session


class TestCircuitBreaker:
    def test_is_open_no_state(self):
        session = _make_neo4j_session(initial_failures=None)
        cb = CircuitBreaker(threshold=3)
        assert cb.is_open(session, "test_module") is False

    def test_is_open_below_threshold(self):
        session = _make_neo4j_session(initial_failures=2)
        cb = CircuitBreaker(threshold=3)
        assert cb.is_open(session, "test_module") is False

    def test_is_open_at_threshold(self):
        session = _make_neo4j_session(initial_failures=3)
        cb = CircuitBreaker(threshold=3)
        assert cb.is_open(session, "test_module") is True

    def test_is_open_above_threshold(self):
        session = _make_neo4j_session(initial_failures=5)
        cb = CircuitBreaker(threshold=3)
        assert cb.is_open(session, "test_module") is True

    def test_record_failure_increments(self):
        session = _make_neo4j_session(initial_failures=None)
        cb = CircuitBreaker(threshold=3)

        cb.record_failure(session, "test_module")
        assert cb.get_failure_count(session, "test_module") == 1

        cb.record_failure(session, "test_module")
        assert cb.get_failure_count(session, "test_module") == 2

        cb.record_failure(session, "test_module")
        assert cb.get_failure_count(session, "test_module") == 3
        assert cb.is_open(session, "test_module") is True

    def test_record_success_resets(self):
        session = _make_neo4j_session(initial_failures=3)
        cb = CircuitBreaker(threshold=3)

        assert cb.is_open(session, "test_module") is True
        cb.record_success(session, "test_module")
        assert cb.get_failure_count(session, "test_module") == 0
        assert cb.is_open(session, "test_module") is False

    def test_custom_threshold(self):
        session = _make_neo4j_session(initial_failures=4)
        cb = CircuitBreaker(threshold=5)
        assert cb.is_open(session, "test_module") is False

        session = _make_neo4j_session(initial_failures=5)
        cb = CircuitBreaker(threshold=5)
        assert cb.is_open(session, "test_module") is True

    def test_is_open_custom_threshold_override(self):
        session = _make_neo4j_session(initial_failures=2)
        cb = CircuitBreaker(threshold=5)
        # Override threshold to 2 for this check
        assert cb.is_open(session, "test_module", threshold=2) is True

    def test_failure_then_success_then_failure(self):
        session = _make_neo4j_session(initial_failures=None)
        cb = CircuitBreaker(threshold=3)

        cb.record_failure(session, "test_module")
        cb.record_failure(session, "test_module")
        assert cb.get_failure_count(session, "test_module") == 2

        cb.record_success(session, "test_module")
        assert cb.get_failure_count(session, "test_module") == 0

        cb.record_failure(session, "test_module")
        assert cb.get_failure_count(session, "test_module") == 1
        assert cb.is_open(session, "test_module") is False

    def test_get_failure_count_no_state(self):
        session = _make_neo4j_session(initial_failures=None)
        cb = CircuitBreaker()
        assert cb.get_failure_count(session, "nonexistent_module") == 0
