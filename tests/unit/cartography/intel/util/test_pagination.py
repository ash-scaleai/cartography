"""
Tests for cartography.intel.util.pagination helpers.
"""

from unittest.mock import MagicMock

import pytest

from cartography.intel.util.pagination import paginated_get
from cartography.intel.util.pagination import paginated_get_aws
from cartography.intel.util.pagination import rebatch


# ---------------------------------------------------------------------------
# paginated_get_aws
# ---------------------------------------------------------------------------


class TestPaginatedGetAws:
    def test_yields_pages(self):
        """Each page from the AWS paginator should be yielded as a separate list."""
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Reservations": [{"id": "r-1"}, {"id": "r-2"}]},
            {"Reservations": [{"id": "r-3"}]},
        ]

        pages = list(paginated_get_aws(paginator, "Reservations"))

        assert len(pages) == 2
        assert pages[0] == [{"id": "r-1"}, {"id": "r-2"}]
        assert pages[1] == [{"id": "r-3"}]

    def test_skips_empty_pages(self):
        """Pages with an empty result list should be skipped."""
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Buckets": [{"Name": "b1"}]},
            {"Buckets": []},
            {"Buckets": [{"Name": "b2"}]},
        ]

        pages = list(paginated_get_aws(paginator, "Buckets"))

        assert len(pages) == 2

    def test_missing_result_key_yields_nothing(self):
        """If the result key is missing entirely, treat it as an empty page."""
        paginator = MagicMock()
        paginator.paginate.return_value = [{"SomethingElse": [1, 2]}]

        pages = list(paginated_get_aws(paginator, "Reservations"))

        assert pages == []

    def test_forwards_paginate_kwargs(self):
        """Extra kwargs should be forwarded to paginate()."""
        paginator = MagicMock()
        paginator.paginate.return_value = []

        list(paginated_get_aws(paginator, "Items", MaxResults=50, Filters=["f"]))

        paginator.paginate.assert_called_once_with(MaxResults=50, Filters=["f"])

    def test_single_page(self):
        """A single-page result should yield exactly one list."""
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Items": [{"id": 1}, {"id": 2}, {"id": 3}]},
        ]

        pages = list(paginated_get_aws(paginator, "Items"))

        assert len(pages) == 1
        assert len(pages[0]) == 3


# ---------------------------------------------------------------------------
# paginated_get (generic token-based)
# ---------------------------------------------------------------------------


class TestPaginatedGet:
    def test_single_page_no_token(self):
        """When there is no NextToken, yield one page and stop."""

        def fetch(**kwargs):
            return {"Items": [{"id": "a"}]}

        pages = list(paginated_get(fetch, "Items"))

        assert pages == [[{"id": "a"}]]

    def test_multiple_pages(self):
        """Follow NextToken across three pages."""
        responses = [
            {"Items": [{"id": "a"}], "NextToken": "tok1"},
            {"Items": [{"id": "b"}], "NextToken": "tok2"},
            {"Items": [{"id": "c"}]},
        ]
        call_count = {"n": 0}

        def fetch(**kwargs):
            resp = responses[call_count["n"]]
            call_count["n"] += 1
            return resp

        pages = list(paginated_get(fetch, "Items"))

        assert len(pages) == 3
        assert pages[0] == [{"id": "a"}]
        assert pages[1] == [{"id": "b"}]
        assert pages[2] == [{"id": "c"}]

    def test_custom_token_keys(self):
        """Support APIs that use non-standard token key names."""
        responses = [
            {"Data": [1, 2], "Cursor": "c1"},
            {"Data": [3]},
        ]
        call_count = {"n": 0}

        def fetch(**kwargs):
            resp = responses[call_count["n"]]
            call_count["n"] += 1
            return resp

        pages = list(paginated_get(
            fetch, "Data",
            token_request_key="cursor",
            token_response_key="Cursor",
        ))

        assert len(pages) == 2

    def test_passes_initial_kwargs(self):
        """Initial kwargs should be forwarded to the first fetch call."""
        received_kwargs = {}

        def fetch(**kwargs):
            received_kwargs.update(kwargs)
            return {"Items": [{"id": "x"}]}

        list(paginated_get(fetch, "Items", MaxResults=100, Filter="active"))

        assert received_kwargs["MaxResults"] == 100
        assert received_kwargs["Filter"] == "active"

    def test_empty_result_key(self):
        """An empty result list should not yield a page but should stop if no token."""

        def fetch(**kwargs):
            return {"Items": []}

        pages = list(paginated_get(fetch, "Items"))

        assert pages == []

    def test_token_passed_on_subsequent_calls(self):
        """The next-page token must be passed as a kwarg on subsequent calls."""
        calls = []

        def fetch(**kwargs):
            calls.append(dict(kwargs))
            if len(calls) == 1:
                return {"Items": [{"id": 1}], "NextToken": "page2"}
            return {"Items": [{"id": 2}]}

        list(paginated_get(fetch, "Items"))

        assert "NextToken" not in calls[0]
        assert calls[1]["NextToken"] == "page2"


# ---------------------------------------------------------------------------
# rebatch
# ---------------------------------------------------------------------------


class TestRebatch:
    def test_uniform_rebatch(self):
        """Pages that align perfectly with batch_size."""
        pages = iter([[1, 2], [3, 4]])
        batches = list(rebatch(pages, batch_size=2))

        assert batches == [[1, 2], [3, 4]]

    def test_splits_large_pages(self):
        """A single large page should be split into multiple batches."""
        pages = iter([[1, 2, 3, 4, 5]])
        batches = list(rebatch(pages, batch_size=2))

        assert batches == [[1, 2], [3, 4], [5]]

    def test_combines_small_pages(self):
        """Small pages should be combined into full batches."""
        pages = iter([[1], [2], [3], [4], [5]])
        batches = list(rebatch(pages, batch_size=3))

        assert batches == [[1, 2, 3], [4, 5]]

    def test_empty_input(self):
        """An empty generator should yield nothing."""
        batches = list(rebatch(iter([]), batch_size=10))
        assert batches == []

    def test_invalid_batch_size(self):
        with pytest.raises(ValueError, match="batch_size must be greater than 0"):
            list(rebatch(iter([]), batch_size=0))

    def test_preserves_all_records(self):
        """Total record count should be the same before and after rebatching."""
        pages = [[{"id": i} for i in range(7)], [{"id": i} for i in range(3)]]
        batches = list(rebatch(iter(pages), batch_size=4))

        total_in = sum(len(p) for p in pages)
        total_out = sum(len(b) for b in batches)
        assert total_in == total_out == 10
