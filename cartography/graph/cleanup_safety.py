import logging
import time
from typing import Optional

import neo4j

logger = logging.getLogger(__name__)

# Default threshold: if current count is below 50% of previous count, skip cleanup
DEFAULT_CLEANUP_THRESHOLD = 0.5


def get_previous_record_count(
    neo4j_session: neo4j.Session,
    module_name: str,
) -> Optional[int]:
    """
    Retrieve the previous record count for a module from the CleanupSyncMetadata node.

    Args:
        neo4j_session: Active Neo4j session.
        module_name: The module/node label identifier (e.g., 'AWSEC2Instance').

    Returns:
        The previous record count, or None if no metadata exists yet (first run).
    """
    result = neo4j_session.run(
        "MATCH (n:CleanupSyncMetadata {module_name: $module_name}) "
        "RETURN n.last_record_count AS last_record_count",
        module_name=module_name,
    )
    record = result.single()
    if record is None:
        return None
    return record["last_record_count"]


def update_record_count(
    neo4j_session: neo4j.Session,
    module_name: str,
    record_count: int,
) -> None:
    """
    Create or update the CleanupSyncMetadata node for a module with the current record count.

    Args:
        neo4j_session: Active Neo4j session.
        module_name: The module/node label identifier (e.g., 'AWSEC2Instance').
        record_count: The number of records fetched in the current sync.
    """
    neo4j_session.run(
        "MERGE (n:CleanupSyncMetadata {module_name: $module_name}) "
        "ON CREATE SET n.firstseen = timestamp() "
        "SET n.last_record_count = $record_count, "
        "    n.last_sync_time = $sync_time",
        module_name=module_name,
        record_count=record_count,
        sync_time=int(time.time()),
    )


def should_skip_cleanup(
    neo4j_session: neo4j.Session,
    module_name: str,
    current_count: int,
    threshold: float = DEFAULT_CLEANUP_THRESHOLD,
) -> bool:
    """
    Determine whether cleanup should be skipped based on the safety net check.

    Compares the current record count against the previous run's count. If the current
    count is below the configured threshold percentage of the previous count, cleanup
    is skipped to prevent accidental data loss from partial fetches or API failures.

    After the check, the current count is always recorded for the next run.

    Args:
        neo4j_session: Active Neo4j session.
        module_name: The module/node label identifier (e.g., 'AWSEC2Instance').
        current_count: The number of records fetched in the current sync.
        threshold: The minimum ratio of current/previous counts required to proceed
            with cleanup. Default is 0.5 (50%).

    Returns:
        True if cleanup should be skipped (count dropped below threshold),
        False if cleanup should proceed.
    """
    previous_count = get_previous_record_count(neo4j_session, module_name)

    # Always update the record count for next run
    update_record_count(neo4j_session, module_name, current_count)

    # First run: no previous data, proceed with cleanup
    if previous_count is None:
        logger.info(
            "Module %s: first run with %d records. No previous count to compare. "
            "Proceeding with cleanup.",
            module_name,
            current_count,
        )
        return False

    # Previous count was 0: avoid division issues, proceed with cleanup
    if previous_count == 0:
        logger.info(
            "Module %s fetched %d records (previous: 0). Proceeding with cleanup.",
            module_name,
            current_count,
        )
        return False

    ratio = current_count / previous_count

    if ratio < threshold:
        logger.warning(
            "Module %s fetched %d records (previous: %d, ratio: %.1f%%, threshold: %.1f%%). "
            "Skipping cleanup to prevent accidental data loss.",
            module_name,
            current_count,
            previous_count,
            ratio * 100,
            threshold * 100,
        )
        return True

    logger.info(
        "Module %s fetched %d records (previous: %d, ratio: %.1f%%, threshold: %.1f%%). "
        "Proceeding with cleanup.",
        module_name,
        current_count,
        previous_count,
        ratio * 100,
        threshold * 100,
    )
    return False
