import logging
from typing import List
from typing import Optional

import neo4j

from cartography.graph.anomaly_detection import AnomalyAlert
from cartography.graph.anomaly_detection import create_anomaly_alert
from cartography.graph.anomaly_detection import DEFAULT_ANOMALY_STD_DEVS
from cartography.graph.anomaly_detection import is_anomalous
from cartography.graph.circuit_breaker import CircuitBreaker
from cartography.graph.circuit_breaker import DEFAULT_CIRCUIT_BREAKER_THRESHOLD
from cartography.graph.cleanup_history import DEFAULT_HISTORY_SIZE
from cartography.graph.cleanup_history import RecordCountHistory

logger = logging.getLogger(__name__)

# Phase 0.4 basic threshold: if a cleanup would remove more than this
# fraction of records, block it by default.
DEFAULT_CLEANUP_THRESHOLD = 0.9


class CleanupSafety:
    """
    Extended cleanup safety net integrating Phase 0.4 threshold checks with
    historical trending, anomaly detection, and circuit breaker.

    This class orchestrates three safety mechanisms:
    1. **History tracking**: Records counts after every sync so trends can
       be analyzed.
    2. **Anomaly detection**: Flags counts that deviate significantly from
       the rolling average before cleanup runs.
    3. **Circuit breaker**: Blocks syncs for modules that have failed
       repeatedly in succession.

    All three mechanisms are additive to the Phase 0.4 basic threshold
    check (which blocks cleanup if it would remove more than a configurable
    fraction of records).

    Args:
        history_size: Number of historical counts to retain per module.
        anomaly_std_devs: Number of standard deviations to trigger anomaly.
        circuit_breaker_threshold: Consecutive failures to trip the circuit breaker.
        cleanup_threshold: Phase 0.4 fraction threshold for blocking cleanup.
    """

    def __init__(
        self,
        history_size: int = DEFAULT_HISTORY_SIZE,
        anomaly_std_devs: float = DEFAULT_ANOMALY_STD_DEVS,
        circuit_breaker_threshold: int = DEFAULT_CIRCUIT_BREAKER_THRESHOLD,
        cleanup_threshold: float = DEFAULT_CLEANUP_THRESHOLD,
    ):
        self.history = RecordCountHistory(history_size=history_size)
        self.circuit_breaker = CircuitBreaker(threshold=circuit_breaker_threshold)
        self.anomaly_std_devs = anomaly_std_devs
        self.cleanup_threshold = cleanup_threshold

    def check_cleanup_safe(
        self,
        neo4j_session: neo4j.Session,
        module_name: str,
        current_count: int,
        previous_count: Optional[int] = None,
    ) -> tuple[bool, str]:
        """
        Determine whether it is safe to proceed with cleanup for a module.

        Runs the following checks in order:
        1. Circuit breaker: if open, blocks immediately.
        2. Phase 0.4 threshold: if previous_count is provided and cleanup
           would remove > cleanup_threshold fraction, blocks.
        3. Anomaly detection: if current count is anomalous relative to
           history, blocks.

        Args:
            neo4j_session: Active Neo4j session.
            module_name: Identifier for the module.
            current_count: The current record count.
            previous_count: The previous record count (for Phase 0.4 check).
                If None, the Phase 0.4 threshold check is skipped.

        Returns:
            Tuple of (is_safe, reason). If safe, reason is empty.
        """
        # Check 1: Circuit breaker
        if self.circuit_breaker.is_open(neo4j_session, module_name):
            reason = (
                f"Circuit breaker is OPEN for module '{module_name}'. "
                f"Skipping cleanup."
            )
            logger.warning(reason)
            return False, reason

        # Check 2: Phase 0.4 basic threshold
        if previous_count is not None and previous_count > 0:
            removal_fraction = (previous_count - current_count) / previous_count
            if removal_fraction > self.cleanup_threshold:
                reason = (
                    f"Cleanup for module '{module_name}' would remove "
                    f"{removal_fraction:.1%} of records (threshold: "
                    f"{self.cleanup_threshold:.1%}). Blocking cleanup."
                )
                logger.warning(reason)
                return False, reason

        # Check 3: Anomaly detection
        history = self.history.get_history(neo4j_session, module_name)
        anomalous, anomaly_reason = is_anomalous(
            current_count, history, self.anomaly_std_devs,
        )
        if anomalous:
            reason = (
                f"Anomaly detected for module '{module_name}': {anomaly_reason}. "
                f"Blocking cleanup."
            )
            logger.warning(reason)
            return False, reason

        return True, ""

    def record_count(
        self,
        neo4j_session: neo4j.Session,
        module_name: str,
        count: int,
    ) -> None:
        """
        Record a count in history after a successful sync.

        Should be called after every sync completes to build up the
        historical data needed for anomaly detection.

        Args:
            neo4j_session: Active Neo4j session.
            module_name: Identifier for the module.
            count: The record count to store.
        """
        self.history.add_count(neo4j_session, module_name, count)

    def record_sync_success(
        self,
        neo4j_session: neo4j.Session,
        module_name: str,
    ) -> None:
        """
        Record a successful sync, resetting the circuit breaker.

        Args:
            neo4j_session: Active Neo4j session.
            module_name: Identifier for the module.
        """
        self.circuit_breaker.record_success(neo4j_session, module_name)

    def record_sync_failure(
        self,
        neo4j_session: neo4j.Session,
        module_name: str,
    ) -> None:
        """
        Record a sync failure, incrementing the circuit breaker.

        Args:
            neo4j_session: Active Neo4j session.
            module_name: Identifier for the module.
        """
        self.circuit_breaker.record_failure(neo4j_session, module_name)

    def get_anomaly_alert(
        self,
        neo4j_session: neo4j.Session,
        module_name: str,
        current_count: int,
    ) -> Optional[AnomalyAlert]:
        """
        Check for an anomaly and return an alert if one is detected.

        Args:
            neo4j_session: Active Neo4j session.
            module_name: Identifier for the module.
            current_count: The current record count.

        Returns:
            An AnomalyAlert if anomalous, None otherwise.
        """
        history = self.history.get_history(neo4j_session, module_name)
        return create_anomaly_alert(
            module_name, current_count, history, self.anomaly_std_devs,
        )


# ─── Backward-compatible standalone function (used by job.py from Phase 0.4) ─

_default_safety = CleanupSafety()


def should_skip_cleanup(
    neo4j_session: neo4j.Session,
    module_name: str,
    current_count: int,
    threshold: float = DEFAULT_CLEANUP_THRESHOLD,
) -> bool:
    """
    Backward-compatible wrapper around CleanupSafety.check_cleanup_safe().

    Returns True if cleanup should be skipped (unsafe), False if it should proceed.
    """
    safety = CleanupSafety(cleanup_threshold=threshold)
    is_safe, reason = safety.check_cleanup_safe(
        neo4j_session, module_name, current_count,
    )
    if not is_safe:
        logger.warning("should_skip_cleanup: %s", reason)
    return not is_safe
