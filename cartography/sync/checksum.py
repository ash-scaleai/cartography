import hashlib
import json
import logging
from typing import Any
from typing import Dict
from typing import List

import neo4j

from cartography.client.core.tx import read_list_of_dicts_tx
from cartography.client.core.tx import run_write_query

logger = logging.getLogger(__name__)


def compute_checksum(record: dict) -> str:
    """
    Compute a deterministic SHA-256 checksum for a record.

    Keys are sorted and values are serialized to JSON with sorted keys and no
    unnecessary whitespace.  This guarantees that two dicts with the same
    key/value pairs always produce the same hash regardless of insertion order.

    :param record: A dictionary representing a single resource record.
    :return: A hex-encoded SHA-256 digest string.
    """
    serialized = json.dumps(record, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class ChecksumStore:
    """
    Stores and retrieves per-resource checksums in Neo4j as ``SyncChecksum`` nodes.

    Each node is keyed by ``(module, resource_id)`` and carries a ``checksum``
    property that holds the SHA-256 hex digest produced by :func:`compute_checksum`.
    """

    # language=Cypher
    _GET_CHECKSUMS_QUERY = """
        MATCH (c:SyncChecksum {module: $module})
        RETURN c.resource_id AS resource_id, c.checksum AS checksum
    """

    # language=Cypher
    _UPSERT_CHECKSUMS_QUERY = """
        UNWIND $records AS rec
        MERGE (c:SyncChecksum {module: $module, resource_id: rec.resource_id})
        SET c.checksum = rec.checksum,
            c.lastupdated = $lastupdated
    """

    # language=Cypher
    _CREATE_INDEX_QUERY = (
        "CREATE INDEX IF NOT EXISTS FOR (c:SyncChecksum) ON (c.module, c.resource_id)"
    )

    def __init__(self, neo4j_session: neo4j.Session) -> None:
        self._session = neo4j_session
        self._ensure_index()

    def _ensure_index(self) -> None:
        self._session.run(self._CREATE_INDEX_QUERY)

    def get_checksums(self, module_name: str) -> Dict[str, str]:
        """
        Return a ``{resource_id: checksum}`` mapping for all known resources
        in the given module.
        """
        rows: List[Dict[str, Any]] = self._session.execute_read(
            read_list_of_dicts_tx,
            self._GET_CHECKSUMS_QUERY,
            module=module_name,
        )
        return {row["resource_id"]: row["checksum"] for row in rows}

    def update_checksums(
        self,
        records: List[Dict[str, Any]],
        module_name: str,
        id_field: str = "id",
        lastupdated: int = 0,
    ) -> None:
        """
        Bulk-upsert checksums for the supplied records.

        :param records: The raw data dicts that were ingested.
        :param module_name: Logical module identifier, e.g. ``"ec2:instance"``.
        :param id_field: The key inside each record dict that holds the resource id.
        :param lastupdated: Timestamp / update tag to store on the checksum node.
        """
        checksum_rows = [
            {
                "resource_id": str(record[id_field]),
                "checksum": compute_checksum(record),
            }
            for record in records
        ]
        if not checksum_rows:
            return
        run_write_query(
            self._session,
            self._UPSERT_CHECKSUMS_QUERY,
            records=checksum_rows,
            module=module_name,
            lastupdated=lastupdated,
        )


def filter_unchanged(
    records: List[Dict[str, Any]],
    module_name: str,
    neo4j_session: neo4j.Session,
    id_field: str = "id",
) -> List[Dict[str, Any]]:
    """
    Return only records whose checksum differs from the value stored in Neo4j.

    On the first run (no stored checksums) every record is returned.

    :param records: Raw data dicts fetched from the upstream API.
    :param module_name: Logical module identifier.
    :param neo4j_session: An open Neo4j session.
    :param id_field: The key inside each record that holds the unique resource id.
    :return: The subset of *records* that have changed or are new.
    """
    store = ChecksumStore(neo4j_session)
    stored = store.get_checksums(module_name)

    changed: List[Dict[str, Any]] = []
    for record in records:
        resource_id = str(record[id_field])
        current_checksum = compute_checksum(record)
        if stored.get(resource_id) != current_checksum:
            changed.append(record)

    return changed


def update_checksums(
    records: List[Dict[str, Any]],
    module_name: str,
    neo4j_session: neo4j.Session,
    id_field: str = "id",
    lastupdated: int = 0,
) -> None:
    """
    Convenience wrapper: bulk-update stored checksums after successful ingestion.
    """
    store = ChecksumStore(neo4j_session)
    store.update_checksums(records, module_name, id_field=id_field, lastupdated=lastupdated)
