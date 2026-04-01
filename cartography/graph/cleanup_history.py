import json
import logging
import math
import time
from typing import List
from typing import Optional

import neo4j

logger = logging.getLogger(__name__)

DEFAULT_HISTORY_SIZE = 10


class RecordCountHistory:
    """
    Tracks historical record counts per module in Neo4j as CleanupHistory nodes.

    Each module gets a single CleanupHistory node with a JSON array property
    storing the last N record counts. This enables rolling average and
    standard deviation calculations for anomaly detection.

    Args:
        history_size: Maximum number of historical counts to retain per module.
            Defaults to 10.
    """

    def __init__(self, history_size: int = DEFAULT_HISTORY_SIZE):
        self.history_size = history_size

    def add_count(
        self,
        neo4j_session: neo4j.Session,
        module_name: str,
        count: int,
    ) -> None:
        """
        Append a record count to the history for the given module.

        If the history exceeds history_size, the oldest entries are trimmed.

        Args:
            neo4j_session: Active Neo4j session.
            module_name: Identifier for the module (e.g. 'aws_ec2').
            count: The record count to store.
        """
        existing = self.get_history(neo4j_session, module_name)
        existing.append(count)
        # Keep only the last N entries
        trimmed = existing[-self.history_size:]
        counts_json = json.dumps(trimmed)
        neo4j_session.run(
            """
            MERGE (h:CleanupHistory {module_name: $module_name})
            SET h.counts = $counts_json,
                h.last_updated = $timestamp
            """,
            module_name=module_name,
            counts_json=counts_json,
            timestamp=int(time.time()),
        )
        logger.debug(
            "Recorded count %d for module '%s'. History: %s",
            count,
            module_name,
            trimmed,
        )

    def get_history(
        self,
        neo4j_session: neo4j.Session,
        module_name: str,
    ) -> List[int]:
        """
        Return the last N record counts for the given module.

        Args:
            neo4j_session: Active Neo4j session.
            module_name: Identifier for the module.

        Returns:
            List of historical counts, oldest first. Empty list if no history exists.
        """
        result = neo4j_session.run(
            """
            MATCH (h:CleanupHistory {module_name: $module_name})
            RETURN h.counts AS counts_json
            """,
            module_name=module_name,
        )
        record = result.single()
        if record is None or record["counts_json"] is None:
            return []
        return json.loads(record["counts_json"])

    def get_rolling_average(
        self,
        neo4j_session: neo4j.Session,
        module_name: str,
    ) -> float:
        """
        Calculate the rolling average of historical counts for a module.

        Args:
            neo4j_session: Active Neo4j session.
            module_name: Identifier for the module.

        Returns:
            The arithmetic mean of stored counts, or 0.0 if no history exists.
        """
        history = self.get_history(neo4j_session, module_name)
        if not history:
            return 0.0
        return sum(history) / len(history)

    def get_standard_deviation(
        self,
        neo4j_session: neo4j.Session,
        module_name: str,
    ) -> float:
        """
        Calculate the population standard deviation of historical counts for a module.

        Args:
            neo4j_session: Active Neo4j session.
            module_name: Identifier for the module.

        Returns:
            The population standard deviation, or 0.0 if fewer than 2 data points.
        """
        history = self.get_history(neo4j_session, module_name)
        if len(history) < 2:
            return 0.0
        mean = sum(history) / len(history)
        variance = sum((x - mean) ** 2 for x in history) / len(history)
        return math.sqrt(variance)
