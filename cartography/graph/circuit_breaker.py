import logging
import time

import neo4j

logger = logging.getLogger(__name__)

DEFAULT_CIRCUIT_BREAKER_THRESHOLD = 3


class CircuitBreaker:
    """
    Tracks consecutive sync failures per module in Neo4j and prevents
    further syncs when failures exceed a threshold.

    State is persisted as CircuitBreakerState nodes in Neo4j so that
    circuit breaker state survives restarts.

    The circuit opens (blocks syncs) after ``threshold`` consecutive failures
    and closes (allows syncs) after a single successful run.

    Args:
        threshold: Number of consecutive failures before the circuit opens.
            Defaults to 3.
    """

    def __init__(self, threshold: int = DEFAULT_CIRCUIT_BREAKER_THRESHOLD):
        self.threshold = threshold

    def record_failure(
        self,
        neo4j_session: neo4j.Session,
        module_name: str,
    ) -> None:
        """
        Increment the consecutive failure count for a module.

        Args:
            neo4j_session: Active Neo4j session.
            module_name: Identifier for the module.
        """
        neo4j_session.run(
            """
            MERGE (cb:CircuitBreakerState {module_name: $module_name})
            ON CREATE SET cb.consecutive_failures = 1, cb.last_updated = $timestamp
            ON MATCH SET cb.consecutive_failures = cb.consecutive_failures + 1,
                         cb.last_updated = $timestamp
            """,
            module_name=module_name,
            timestamp=int(time.time()),
        )
        logger.warning(
            "Recorded failure for module '%s'.",
            module_name,
        )

    def record_success(
        self,
        neo4j_session: neo4j.Session,
        module_name: str,
    ) -> None:
        """
        Reset the failure count for a module, closing the circuit.

        Args:
            neo4j_session: Active Neo4j session.
            module_name: Identifier for the module.
        """
        neo4j_session.run(
            """
            MERGE (cb:CircuitBreakerState {module_name: $module_name})
            SET cb.consecutive_failures = 0, cb.last_updated = $timestamp
            """,
            module_name=module_name,
            timestamp=int(time.time()),
        )
        logger.debug(
            "Recorded success for module '%s'. Circuit closed.",
            module_name,
        )

    def is_open(
        self,
        neo4j_session: neo4j.Session,
        module_name: str,
        threshold: int | None = None,
    ) -> bool:
        """
        Check whether the circuit breaker is open (blocking syncs) for a module.

        Args:
            neo4j_session: Active Neo4j session.
            module_name: Identifier for the module.
            threshold: Override the default threshold for this check. If None,
                uses the instance threshold.

        Returns:
            True if consecutive failures >= threshold (circuit is open),
            False otherwise.
        """
        if threshold is None:
            threshold = self.threshold

        result = neo4j_session.run(
            """
            MATCH (cb:CircuitBreakerState {module_name: $module_name})
            RETURN cb.consecutive_failures AS failures
            """,
            module_name=module_name,
        )
        record = result.single()
        if record is None:
            return False

        failures = record["failures"]
        is_tripped = failures >= threshold
        if is_tripped:
            logger.warning(
                "Circuit breaker OPEN for module '%s': %d consecutive failures "
                "(threshold=%d). Blocking sync.",
                module_name,
                failures,
                threshold,
            )
        return is_tripped

    def get_failure_count(
        self,
        neo4j_session: neo4j.Session,
        module_name: str,
    ) -> int:
        """
        Get the current consecutive failure count for a module.

        Args:
            neo4j_session: Active Neo4j session.
            module_name: Identifier for the module.

        Returns:
            The number of consecutive failures, or 0 if no state exists.
        """
        result = neo4j_session.run(
            """
            MATCH (cb:CircuitBreakerState {module_name: $module_name})
            RETURN cb.consecutive_failures AS failures
            """,
            module_name=module_name,
        )
        record = result.single()
        if record is None:
            return 0
        return record["failures"]
