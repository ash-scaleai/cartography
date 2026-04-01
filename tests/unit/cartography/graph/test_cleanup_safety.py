from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from cartography.graph.cleanup_safety import should_skip_cleanup
from cartography.graph.job import GraphJob
from cartography.graph.statement import GraphStatement


class TestShouldSkipCleanup:
    """Tests for the cleanup safety net logic."""

    @patch('cartography.graph.cleanup_safety.update_record_count')
    @patch('cartography.graph.cleanup_safety.get_previous_record_count')
    def test_skip_cleanup_when_count_drops_below_threshold(
        self, mock_get_prev, mock_update,
    ):
        """If current count is below the threshold ratio of previous, skip cleanup."""
        mock_get_prev.return_value = 100
        neo4j_session = MagicMock()

        result = should_skip_cleanup(
            neo4j_session, module_name='TestModule', current_count=30, threshold=0.5,
        )

        assert result is True
        mock_update.assert_called_once_with(neo4j_session, 'TestModule', 30)

    @patch('cartography.graph.cleanup_safety.update_record_count')
    @patch('cartography.graph.cleanup_safety.get_previous_record_count')
    def test_allow_cleanup_when_count_above_threshold(
        self, mock_get_prev, mock_update,
    ):
        """If current count is at or above the threshold ratio, allow cleanup."""
        mock_get_prev.return_value = 100
        neo4j_session = MagicMock()

        result = should_skip_cleanup(
            neo4j_session, module_name='TestModule', current_count=60, threshold=0.5,
        )

        assert result is False
        mock_update.assert_called_once_with(neo4j_session, 'TestModule', 60)

    @patch('cartography.graph.cleanup_safety.update_record_count')
    @patch('cartography.graph.cleanup_safety.get_previous_record_count')
    def test_allow_cleanup_when_count_exactly_at_threshold(
        self, mock_get_prev, mock_update,
    ):
        """If current count is exactly at the threshold ratio, allow cleanup."""
        mock_get_prev.return_value = 100
        neo4j_session = MagicMock()

        result = should_skip_cleanup(
            neo4j_session, module_name='TestModule', current_count=50, threshold=0.5,
        )

        assert result is False

    @patch('cartography.graph.cleanup_safety.update_record_count')
    @patch('cartography.graph.cleanup_safety.get_previous_record_count')
    def test_first_run_no_previous_count(
        self, mock_get_prev, mock_update,
    ):
        """On first run with no previous count, proceed with cleanup."""
        mock_get_prev.return_value = None
        neo4j_session = MagicMock()

        result = should_skip_cleanup(
            neo4j_session, module_name='TestModule', current_count=50, threshold=0.5,
        )

        assert result is False
        mock_update.assert_called_once_with(neo4j_session, 'TestModule', 50)

    @patch('cartography.graph.cleanup_safety.update_record_count')
    @patch('cartography.graph.cleanup_safety.get_previous_record_count')
    def test_previous_count_zero(
        self, mock_get_prev, mock_update,
    ):
        """If previous count was 0, proceed with cleanup (avoid division by zero)."""
        mock_get_prev.return_value = 0
        neo4j_session = MagicMock()

        result = should_skip_cleanup(
            neo4j_session, module_name='TestModule', current_count=10, threshold=0.5,
        )

        assert result is False

    @patch('cartography.graph.cleanup_safety.update_record_count')
    @patch('cartography.graph.cleanup_safety.get_previous_record_count')
    def test_current_count_zero_skips_cleanup(
        self, mock_get_prev, mock_update,
    ):
        """If current count is 0 and there was previous data, skip cleanup."""
        mock_get_prev.return_value = 100
        neo4j_session = MagicMock()

        result = should_skip_cleanup(
            neo4j_session, module_name='TestModule', current_count=0, threshold=0.5,
        )

        assert result is True

    @patch('cartography.graph.cleanup_safety.update_record_count')
    @patch('cartography.graph.cleanup_safety.get_previous_record_count')
    def test_custom_threshold(
        self, mock_get_prev, mock_update,
    ):
        """Test with a custom threshold of 0.8 (80%)."""
        mock_get_prev.return_value = 100
        neo4j_session = MagicMock()

        # 70% of previous - should skip with 80% threshold
        result = should_skip_cleanup(
            neo4j_session, module_name='TestModule', current_count=70, threshold=0.8,
        )
        assert result is True

        # 85% of previous - should allow with 80% threshold
        result = should_skip_cleanup(
            neo4j_session, module_name='TestModule', current_count=85, threshold=0.8,
        )
        assert result is False


class TestGraphJobRunWithSafety:
    """Tests for the GraphJob.run_with_safety method."""

    def _make_job(self):
        stmt = GraphStatement("MATCH (n:TestNode) WHERE n.lastupdated <> $UPDATE_TAG DETACH DELETE n")
        stmt.merge_parameters({"UPDATE_TAG": 1234})
        return GraphJob("Test cleanup", [stmt], "TestModule")

    @patch('cartography.graph.job.should_skip_cleanup')
    def test_run_with_safety_proceeds_when_safe(self, mock_should_skip):
        """When should_skip_cleanup returns False, the job runs."""
        mock_should_skip.return_value = False
        neo4j_session = MagicMock()
        job = self._make_job()

        with patch.object(job, 'run') as mock_run:
            job.run_with_safety(neo4j_session, current_record_count=100, threshold=0.5)
            mock_run.assert_called_once_with(neo4j_session)

    @patch('cartography.graph.job.should_skip_cleanup')
    def test_run_with_safety_skips_when_unsafe(self, mock_should_skip):
        """When should_skip_cleanup returns True, the job is skipped."""
        mock_should_skip.return_value = True
        neo4j_session = MagicMock()
        job = self._make_job()

        with patch.object(job, 'run') as mock_run:
            job.run_with_safety(neo4j_session, current_record_count=10, threshold=0.5)
            mock_run.assert_not_called()

    def test_run_with_safety_skip_safety_flag(self):
        """When skip_safety=True, the job always runs without checking."""
        neo4j_session = MagicMock()
        job = self._make_job()

        with patch.object(job, 'run') as mock_run, \
             patch('cartography.graph.job.should_skip_cleanup') as mock_should_skip:
            job.run_with_safety(
                neo4j_session, current_record_count=10, threshold=0.5, skip_safety=True,
            )
            mock_should_skip.assert_not_called()
            mock_run.assert_called_once_with(neo4j_session)

    @patch('cartography.graph.job.should_skip_cleanup')
    def test_run_with_safety_uses_short_name_as_module(self, mock_should_skip):
        """Verify that short_name is used as the module name for the safety check."""
        mock_should_skip.return_value = False
        neo4j_session = MagicMock()
        job = self._make_job()

        with patch.object(job, 'run'):
            job.run_with_safety(neo4j_session, current_record_count=100)

        mock_should_skip.assert_called_once_with(
            neo4j_session, 'TestModule', 100, 0.5,
        )

    @patch('cartography.graph.job.should_skip_cleanup')
    def test_run_with_safety_falls_back_to_name(self, mock_should_skip):
        """When short_name is None, use the full job name as module identifier."""
        mock_should_skip.return_value = False
        neo4j_session = MagicMock()
        stmt = GraphStatement("MATCH (n) RETURN n")
        job = GraphJob("Full job name", [stmt], short_name=None)

        with patch.object(job, 'run'):
            job.run_with_safety(neo4j_session, current_record_count=100)

        mock_should_skip.assert_called_once_with(
            neo4j_session, 'Full job name', 100, 0.5,
        )
