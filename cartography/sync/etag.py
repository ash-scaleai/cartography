import logging
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import neo4j

from cartography.client.core.tx import read_list_of_dicts_tx
from cartography.client.core.tx import run_write_query

logger = logging.getLogger(__name__)


class ETagStore:
    """
    Stores and retrieves HTTP ETags per API endpoint in Neo4j as ``SyncETag`` nodes.

    Each node is keyed by ``endpoint`` and carries an ``etag`` property.
    """

    # language=Cypher
    _GET_ETAG_QUERY = """
        MATCH (e:SyncETag {endpoint: $endpoint})
        RETURN e.etag AS etag
    """

    # language=Cypher
    _UPSERT_ETAG_QUERY = """
        MERGE (e:SyncETag {endpoint: $endpoint})
        SET e.etag = $etag,
            e.lastupdated = $lastupdated
    """

    # language=Cypher
    _GET_ALL_ETAGS_QUERY = """
        MATCH (e:SyncETag)
        RETURN e.endpoint AS endpoint, e.etag AS etag
    """

    # language=Cypher
    _CREATE_INDEX_QUERY = (
        "CREATE INDEX IF NOT EXISTS FOR (e:SyncETag) ON (e.endpoint)"
    )

    def __init__(self, neo4j_session: neo4j.Session) -> None:
        self._session = neo4j_session
        self._ensure_index()

    def _ensure_index(self) -> None:
        self._session.run(self._CREATE_INDEX_QUERY)

    def get_etag(self, endpoint: str) -> Optional[str]:
        """
        Retrieve the stored ETag for *endpoint*, or ``None`` if not found.
        """
        rows: List[Dict[str, Any]] = self._session.execute_read(
            read_list_of_dicts_tx,
            self._GET_ETAG_QUERY,
            endpoint=endpoint,
        )
        if rows:
            return rows[0]["etag"]
        return None

    def store_etag(self, endpoint: str, etag: str, lastupdated: int = 0) -> None:
        """
        Persist an ETag value for *endpoint*.
        """
        run_write_query(
            self._session,
            self._UPSERT_ETAG_QUERY,
            endpoint=endpoint,
            etag=etag,
            lastupdated=lastupdated,
        )

    def get_all_etags(self) -> Dict[str, str]:
        """
        Return a mapping of all stored ``{endpoint: etag}`` pairs.
        """
        rows: List[Dict[str, Any]] = self._session.execute_read(
            read_list_of_dicts_tx,
            self._GET_ALL_ETAGS_QUERY,
        )
        return {row["endpoint"]: row["etag"] for row in rows}


def check_etag(endpoint: str, stored_etag: Optional[str]) -> bool:
    """
    Determine whether the data at *endpoint* is unchanged based on its ETag.

    Returns ``True`` if the server responds with HTTP 304 Not Modified (i.e. the
    data has **not** changed), ``False`` otherwise.

    .. note::
       This is a *stub* implementation.  A real implementation would issue a
       conditional HTTP request with an ``If-None-Match`` header.  Since the
       actual HTTP transport varies by provider SDK this function serves as a
       contract / interface that provider-specific code can call or override.

    :param endpoint: The API endpoint URL.
    :param stored_etag: The previously stored ETag, or ``None`` on first run.
    :return: ``True`` when data is unchanged (HTTP 304), ``False`` otherwise.
    """
    if stored_etag is None:
        # First run — no stored ETag, data must be fetched.
        return False

    # Placeholder: real implementations will issue a conditional request here
    # and return True only on HTTP 304.
    logger.debug(
        "ETag check for %s with stored etag %s — full fetch required (stub)",
        endpoint,
        stored_etag,
    )
    return False
