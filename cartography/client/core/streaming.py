"""
Streaming ingestion support for cartography.

This module provides a StreamingLoader that accepts an iterable/generator of record
batches and loads each batch to Neo4j as it arrives, keeping only one batch in memory
at a time. This dramatically reduces peak memory usage for large syncs.

Existing non-streaming modules are unaffected -- this is an opt-in enhancement.
"""

import logging
import time
from typing import Any
from typing import Dict
from typing import Iterable
from typing import List
from typing import Optional

import neo4j

from cartography.client.core.tx import ensure_indexes
from cartography.client.core.tx import load_graph_data
from cartography.graph.querybuilder import build_conditional_label_queries
from cartography.graph.querybuilder import build_ingestion_query
from cartography.client.core.tx import run_write_query
from cartography.models.core.nodes import CartographyNodeSchema
from cartography.stats import get_stats_client

logger = logging.getLogger(__name__)
stat_handler = get_stats_client(__name__)

DEFAULT_BATCH_SIZE = 1000


class StreamingLoader:
    """
    Loads records to Neo4j in a streaming fashion, one batch at a time.

    Instead of collecting all records in memory and then bulk-loading, this
    class accepts an iterable (typically a generator) that yields pages/batches
    of records and loads each batch to Neo4j immediately. This means only one
    batch is held in memory at any given time.

    The update_tag is consistent across all batches in a single sync run so
    that cleanup can correctly identify stale records afterward.

    Usage::

        loader = StreamingLoader(
            neo4j_session=session,
            node_schema=EC2InstanceSchema(),
            update_tag=update_tag,
            batch_size=1000,
            labeling_kwargs={'AWS_ID': account_id, 'Region': region},
        )

        # pages_iter is a generator yielding List[Dict] pages
        total = loader.load_batches(pages_iter)
    """

    def __init__(
        self,
        neo4j_session: neo4j.Session,
        node_schema: CartographyNodeSchema,
        update_tag: int,
        batch_size: int = DEFAULT_BATCH_SIZE,
        labeling_kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize the StreamingLoader.

        :param neo4j_session: The Neo4j session for database operations.
        :param node_schema: The CartographyNodeSchema describing what to load.
        :param update_tag: The update tag (timestamp) for this sync run.
            Must be the same across all batches.
        :param batch_size: Maximum number of records per Neo4j write transaction.
            This controls the UNWIND chunk size sent to Neo4j.
            Defaults to 1000.
        :param labeling_kwargs: Extra keyword arguments forwarded to every
            ``load_graph_data`` call (e.g. ``AWS_ID``, ``Region``).
        """
        if batch_size <= 0:
            raise ValueError(f"batch_size must be greater than 0, got {batch_size}")

        self.neo4j_session = neo4j_session
        self.node_schema = node_schema
        self.update_tag = update_tag
        self.batch_size = batch_size
        self.labeling_kwargs: Dict[str, Any] = labeling_kwargs or {}

        # Pre-build the ingestion query once; it is the same for every batch.
        self._ingestion_query: str = build_ingestion_query(node_schema)
        self._indexes_ensured: bool = False

    def _ensure_indexes_once(self) -> None:
        """Create indexes if we have not already done so in this loader's lifetime."""
        if not self._indexes_ensured:
            ensure_indexes(self.neo4j_session, self.node_schema)
            self._indexes_ensured = True

    def load_batches(
        self,
        record_batches: Iterable[List[Dict[str, Any]]],
        total_batches: Optional[int] = None,
    ) -> int:
        """
        Stream *record_batches* into Neo4j, one batch at a time.

        Each element of *record_batches* is a list of dicts (one "page" of
        records from an API).  The loader writes every page to Neo4j before
        requesting the next one, so only one page is in memory at a time.

        :param record_batches: An iterable (often a generator) that yields
            ``List[Dict[str, Any]]`` pages.
        :param total_batches: If the caller knows how many batches there will
            be, pass it here for nicer progress logging.  ``None`` means
            unknown.
        :return: The total number of records loaded across all batches.
        """
        self._ensure_indexes_once()

        total_records = 0
        batch_number = 0
        label = self.node_schema.label
        start_time = time.monotonic()

        for page in record_batches:
            if not page:
                # Skip empty pages (e.g. the API returned an empty result set)
                continue

            batch_number += 1

            load_graph_data(
                self.neo4j_session,
                self._ingestion_query,
                page,
                batch_size=self.batch_size,
                lastupdated=self.update_tag,
                **self.labeling_kwargs,
            )

            total_records += len(page)

            total_str = str(total_batches) if total_batches is not None else "unknown"
            logger.info(
                "Loaded batch %d/%s (%d records so far) for %s",
                batch_number,
                total_str,
                total_records,
                label,
            )

        elapsed = time.monotonic() - start_time

        # Apply conditional labels if any are defined
        conditional_label_queries = build_conditional_label_queries(self.node_schema)
        for query in conditional_label_queries:
            run_write_query(
                self.neo4j_session,
                query,
                lastupdated=self.update_tag,
                **self.labeling_kwargs,
            )

        # Emit aggregate metrics
        stat_handler.incr(f"node.{label.lower()}.loaded", total_records)
        logger.info(
            "Streaming load complete for %s: %d records in %d batches (%.1fs)",
            label,
            total_records,
            batch_number,
            elapsed,
        )

        return total_records
