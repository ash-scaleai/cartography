"""
Tests for cartography.client.core.streaming.StreamingLoader.
"""

from unittest.mock import MagicMock
from unittest.mock import call
from unittest.mock import patch

import pytest

from cartography.client.core.streaming import DEFAULT_BATCH_SIZE
from cartography.client.core.streaming import StreamingLoader


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_node_schema():
    """Return a minimal mock CartographyNodeSchema."""
    schema = MagicMock()
    schema.label = "TestNode"
    return schema


def _make_session():
    """Return a mock neo4j.Session."""
    return MagicMock()


# ---------------------------------------------------------------------------
# StreamingLoader construction
# ---------------------------------------------------------------------------


class TestStreamingLoaderInit:
    @patch("cartography.client.core.streaming.build_ingestion_query", return_value="Q")
    def test_default_batch_size(self, mock_build):
        loader = StreamingLoader(
            neo4j_session=_make_session(),
            node_schema=_make_node_schema(),
            update_tag=1,
        )
        assert loader.batch_size == DEFAULT_BATCH_SIZE

    @patch("cartography.client.core.streaming.build_ingestion_query", return_value="Q")
    def test_custom_batch_size(self, mock_build):
        loader = StreamingLoader(
            neo4j_session=_make_session(),
            node_schema=_make_node_schema(),
            update_tag=1,
            batch_size=500,
        )
        assert loader.batch_size == 500

    def test_invalid_batch_size_raises(self):
        with pytest.raises(ValueError, match="batch_size must be greater than 0"):
            StreamingLoader(
                neo4j_session=_make_session(),
                node_schema=_make_node_schema(),
                update_tag=1,
                batch_size=0,
            )

    def test_negative_batch_size_raises(self):
        with pytest.raises(ValueError, match="batch_size must be greater than 0"):
            StreamingLoader(
                neo4j_session=_make_session(),
                node_schema=_make_node_schema(),
                update_tag=1,
                batch_size=-1,
            )


# ---------------------------------------------------------------------------
# load_batches
# ---------------------------------------------------------------------------


class TestStreamingLoaderLoadBatches:
    @patch("cartography.client.core.streaming.build_conditional_label_queries", return_value=[])
    @patch("cartography.client.core.streaming.load_graph_data")
    @patch("cartography.client.core.streaming.ensure_indexes")
    @patch("cartography.client.core.streaming.build_ingestion_query", return_value="UNWIND $DictList AS d ...")
    def test_processes_multiple_batches(
        self, mock_build, mock_ensure, mock_load, mock_cond,
    ):
        """Each page yielded by the generator should produce one load_graph_data call."""
        session = _make_session()
        schema = _make_node_schema()

        loader = StreamingLoader(
            neo4j_session=session,
            node_schema=schema,
            update_tag=42,
            batch_size=100,
        )

        pages = [
            [{"id": "a"}, {"id": "b"}],
            [{"id": "c"}],
            [{"id": "d"}, {"id": "e"}, {"id": "f"}],
        ]

        total = loader.load_batches(iter(pages))

        assert total == 6
        assert mock_load.call_count == 3
        mock_ensure.assert_called_once_with(session, schema)

    @patch("cartography.client.core.streaming.build_conditional_label_queries", return_value=[])
    @patch("cartography.client.core.streaming.load_graph_data")
    @patch("cartography.client.core.streaming.ensure_indexes")
    @patch("cartography.client.core.streaming.build_ingestion_query", return_value="Q")
    def test_all_records_loaded_no_data_loss(
        self, mock_build, mock_ensure, mock_load, mock_cond,
    ):
        """Verify that the total count matches the sum of all page sizes."""
        loader = StreamingLoader(
            neo4j_session=_make_session(),
            node_schema=_make_node_schema(),
            update_tag=1,
            batch_size=1000,
        )

        pages = [[{"id": i} for i in range(10)] for _ in range(5)]
        total = loader.load_batches(iter(pages))

        assert total == 50

        # Each call should have received the right page
        for i, c in enumerate(mock_load.call_args_list):
            assert c.args[2] == pages[i]  # dict_list positional arg

    @patch("cartography.client.core.streaming.build_conditional_label_queries", return_value=[])
    @patch("cartography.client.core.streaming.load_graph_data")
    @patch("cartography.client.core.streaming.ensure_indexes")
    @patch("cartography.client.core.streaming.build_ingestion_query", return_value="Q")
    def test_empty_pages_skipped(
        self, mock_build, mock_ensure, mock_load, mock_cond,
    ):
        """Empty pages should be silently skipped without a Neo4j call."""
        loader = StreamingLoader(
            neo4j_session=_make_session(),
            node_schema=_make_node_schema(),
            update_tag=1,
        )

        pages = [[], [{"id": "a"}], [], [{"id": "b"}], []]
        total = loader.load_batches(iter(pages))

        assert total == 2
        assert mock_load.call_count == 2

    @patch("cartography.client.core.streaming.build_conditional_label_queries", return_value=[])
    @patch("cartography.client.core.streaming.load_graph_data")
    @patch("cartography.client.core.streaming.ensure_indexes")
    @patch("cartography.client.core.streaming.build_ingestion_query", return_value="Q")
    def test_empty_generator_returns_zero(
        self, mock_build, mock_ensure, mock_load, mock_cond,
    ):
        """An entirely empty generator should return 0 and make no Neo4j calls."""
        loader = StreamingLoader(
            neo4j_session=_make_session(),
            node_schema=_make_node_schema(),
            update_tag=1,
        )

        total = loader.load_batches(iter([]))

        assert total == 0
        mock_load.assert_not_called()

    @patch("cartography.client.core.streaming.build_conditional_label_queries", return_value=[])
    @patch("cartography.client.core.streaming.load_graph_data")
    @patch("cartography.client.core.streaming.ensure_indexes")
    @patch("cartography.client.core.streaming.build_ingestion_query", return_value="Q")
    def test_update_tag_consistent_across_batches(
        self, mock_build, mock_ensure, mock_load, mock_cond,
    ):
        """Every batch must be loaded with the same lastupdated value."""
        update_tag = 99999
        loader = StreamingLoader(
            neo4j_session=_make_session(),
            node_schema=_make_node_schema(),
            update_tag=update_tag,
        )

        pages = [[{"id": "a"}], [{"id": "b"}]]
        loader.load_batches(iter(pages))

        for c in mock_load.call_args_list:
            assert c.kwargs["lastupdated"] == update_tag

    @patch("cartography.client.core.streaming.build_conditional_label_queries", return_value=[])
    @patch("cartography.client.core.streaming.load_graph_data")
    @patch("cartography.client.core.streaming.ensure_indexes")
    @patch("cartography.client.core.streaming.build_ingestion_query", return_value="Q")
    def test_labeling_kwargs_forwarded(
        self, mock_build, mock_ensure, mock_load, mock_cond,
    ):
        """Extra kwargs like AWS_ID and Region must appear in every load call."""
        loader = StreamingLoader(
            neo4j_session=_make_session(),
            node_schema=_make_node_schema(),
            update_tag=1,
            labeling_kwargs={"AWS_ID": "123", "Region": "us-east-1"},
        )

        loader.load_batches(iter([[{"id": "x"}]]))

        _, kwargs = mock_load.call_args
        assert kwargs["AWS_ID"] == "123"
        assert kwargs["Region"] == "us-east-1"

    @patch("cartography.client.core.streaming.build_conditional_label_queries", return_value=[])
    @patch("cartography.client.core.streaming.load_graph_data")
    @patch("cartography.client.core.streaming.ensure_indexes")
    @patch("cartography.client.core.streaming.build_ingestion_query", return_value="Q")
    def test_batch_size_forwarded_to_load_graph_data(
        self, mock_build, mock_ensure, mock_load, mock_cond,
    ):
        """The configured batch_size must be forwarded to load_graph_data."""
        loader = StreamingLoader(
            neo4j_session=_make_session(),
            node_schema=_make_node_schema(),
            update_tag=1,
            batch_size=42,
        )

        loader.load_batches(iter([[{"id": "x"}]]))

        _, kwargs = mock_load.call_args
        assert kwargs["batch_size"] == 42

    @patch("cartography.client.core.streaming.logger")
    @patch("cartography.client.core.streaming.build_conditional_label_queries", return_value=[])
    @patch("cartography.client.core.streaming.load_graph_data")
    @patch("cartography.client.core.streaming.ensure_indexes")
    @patch("cartography.client.core.streaming.build_ingestion_query", return_value="Q")
    def test_progress_logging(
        self, mock_build, mock_ensure, mock_load, mock_cond, mock_logger,
    ):
        """Progress log messages should include batch number, record count, and label."""
        loader = StreamingLoader(
            neo4j_session=_make_session(),
            node_schema=_make_node_schema(),
            update_tag=1,
        )

        pages = [[{"id": "a"}, {"id": "b"}], [{"id": "c"}]]
        loader.load_batches(iter(pages))

        info_calls = [c for c in mock_logger.info.call_args_list]

        # First batch log
        first_msg = info_calls[0]
        assert first_msg == call(
            "Loaded batch %d/%s (%d records so far) for %s",
            1, "unknown", 2, "TestNode",
        )

        # Second batch log
        second_msg = info_calls[1]
        assert second_msg == call(
            "Loaded batch %d/%s (%d records so far) for %s",
            2, "unknown", 3, "TestNode",
        )

    @patch("cartography.client.core.streaming.logger")
    @patch("cartography.client.core.streaming.build_conditional_label_queries", return_value=[])
    @patch("cartography.client.core.streaming.load_graph_data")
    @patch("cartography.client.core.streaming.ensure_indexes")
    @patch("cartography.client.core.streaming.build_ingestion_query", return_value="Q")
    def test_progress_logging_with_known_total(
        self, mock_build, mock_ensure, mock_load, mock_cond, mock_logger,
    ):
        """When total_batches is known, it should appear in the log message."""
        loader = StreamingLoader(
            neo4j_session=_make_session(),
            node_schema=_make_node_schema(),
            update_tag=1,
        )

        pages = [[{"id": "a"}], [{"id": "b"}]]
        loader.load_batches(iter(pages), total_batches=2)

        first_msg = mock_logger.info.call_args_list[0]
        assert first_msg == call(
            "Loaded batch %d/%s (%d records so far) for %s",
            1, "2", 1, "TestNode",
        )

    @patch("cartography.client.core.streaming.build_conditional_label_queries", return_value=[])
    @patch("cartography.client.core.streaming.load_graph_data")
    @patch("cartography.client.core.streaming.ensure_indexes")
    @patch("cartography.client.core.streaming.build_ingestion_query", return_value="Q")
    def test_indexes_only_created_once(
        self, mock_build, mock_ensure, mock_load, mock_cond,
    ):
        """Even when load_batches is called multiple times, indexes are created only once."""
        session = _make_session()
        schema = _make_node_schema()
        loader = StreamingLoader(
            neo4j_session=session,
            node_schema=schema,
            update_tag=1,
        )

        loader.load_batches(iter([[{"id": "a"}]]))
        loader.load_batches(iter([[{"id": "b"}]]))

        mock_ensure.assert_called_once()

    @patch("cartography.client.core.streaming.build_conditional_label_queries", return_value=[])
    @patch("cartography.client.core.streaming.load_graph_data")
    @patch("cartography.client.core.streaming.ensure_indexes")
    @patch("cartography.client.core.streaming.build_ingestion_query", return_value="Q")
    def test_works_with_generator(
        self, mock_build, mock_ensure, mock_load, mock_cond,
    ):
        """Must work with a true generator (not just a list)."""

        def page_gen():
            yield [{"id": "1"}, {"id": "2"}]
            yield [{"id": "3"}]

        loader = StreamingLoader(
            neo4j_session=_make_session(),
            node_schema=_make_node_schema(),
            update_tag=1,
        )

        total = loader.load_batches(page_gen())
        assert total == 3
        assert mock_load.call_count == 2
