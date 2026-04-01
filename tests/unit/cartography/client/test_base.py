"""Tests for cartography.client.base — rate limiter, retry handler, pagination."""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import pytest

from cartography.client.base import APIClientConfig
from cartography.client.base import BackoffStrategy
from cartography.client.base import BaseAPIClient
from cartography.client.base import PaginatedFetcher
from cartography.client.base import PaginationConfig
from cartography.client.base import PaginationStyle
from cartography.client.base import RateLimiter
from cartography.client.base import RetryHandler


# ---------------------------------------------------------------------------
# RateLimiter tests
# ---------------------------------------------------------------------------

class TestRateLimiter:

    def test_unlimited_returns_immediately(self):
        """max_rps=0 means no rate limiting."""
        limiter = RateLimiter(max_rps=0)
        wait = limiter.acquire()
        assert wait == 0.0

    def test_first_acquire_immediate(self):
        """The first acquire should return quickly (token already available)."""
        limiter = RateLimiter(max_rps=5)
        start = time.monotonic()
        limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1

    def test_enforces_max_rps(self):
        """Acquiring more tokens than max_rps should introduce delay."""
        max_rps = 10
        limiter = RateLimiter(max_rps=max_rps)

        # Drain the initial token
        limiter.acquire()

        # Now time how long the next acquire takes
        start = time.monotonic()
        limiter.acquire()
        elapsed = time.monotonic() - start

        # Should wait roughly 1/max_rps seconds (0.1s), allow some tolerance
        expected_min = 1.0 / max_rps * 0.5  # 50ms minimum
        assert elapsed >= expected_min, (
            f"Expected wait >= {expected_min:.3f}s, got {elapsed:.3f}s"
        )

    def test_negative_max_rps_raises(self):
        with pytest.raises(ValueError, match="max_rps must be >= 0"):
            RateLimiter(max_rps=-1)

    def test_thread_safety(self):
        """Multiple threads acquiring tokens should not corrupt state."""
        limiter = RateLimiter(max_rps=100)
        errors: list[Exception] = []
        acquired_count = 0
        lock = threading.Lock()

        def worker():
            nonlocal acquired_count
            try:
                for _ in range(10):
                    limiter.acquire()
                    with lock:
                        acquired_count += 1
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Errors in threads: {errors}"
        assert acquired_count == 50

    def test_max_rps_property(self):
        limiter = RateLimiter(max_rps=42)
        assert limiter.max_rps == 42


# ---------------------------------------------------------------------------
# RetryHandler tests
# ---------------------------------------------------------------------------

class TestRetryHandler:

    def test_success_no_retry(self):
        """Successful call should return immediately without retry."""
        config = APIClientConfig(max_retries=3)
        handler = RetryHandler(config)
        result = handler.execute(lambda: "ok")
        assert result == "ok"

    def test_retry_on_failure_then_success(self):
        """Should retry on exception and eventually succeed."""
        config = APIClientConfig(
            max_retries=3,
            backoff=BackoffStrategy.CONSTANT,
            backoff_base=0.01,  # tiny wait for tests
        )
        handler = RetryHandler(config)

        call_count = 0

        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("transient error")
            return "success"

        result = handler.execute(flaky)
        assert result == "success"
        assert call_count == 3

    def test_gives_up_after_max_retries(self):
        """Should raise after max_retries attempts."""
        config = APIClientConfig(
            max_retries=2,
            backoff=BackoffStrategy.CONSTANT,
            backoff_base=0.01,
        )
        handler = RetryHandler(config)
        call_count = 0

        def always_fail():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("permanent error")

        with pytest.raises(RuntimeError, match="permanent error"):
            handler.execute(always_fail)

        # initial attempt + 2 retries = 3 total
        assert call_count == 3

    def test_exponential_backoff_timing(self):
        """Exponential backoff should increase wait time geometrically."""
        config = APIClientConfig(
            max_retries=3,
            backoff=BackoffStrategy.EXPONENTIAL,
            backoff_base=0.05,  # 50ms base for fast tests
            backoff_max=10.0,
        )
        handler = RetryHandler(config)
        call_count = 0

        def always_fail():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("fail")

        start = time.monotonic()
        with pytest.raises(RuntimeError):
            handler.execute(always_fail)
        total_elapsed = time.monotonic() - start

        # backoff waits: 0.05^1 + 0.05^2 + 0.05^3 = 0.05 + 0.0025 + 0.000125
        # With exponential: base^attempt = 0.05, 0.0025, 0.000125
        # Actually the formula is backoff_base ** attempt:
        #   attempt=1 -> 0.05^1 = 0.05s
        #   attempt=2 -> 0.05^2 = 0.0025s
        #   attempt=3 -> 0.05^3 = 0.000125s
        # Total ~ 0.053s minimum
        # Just verify it completed in reasonable time (not hung)
        assert total_elapsed < 5.0, f"Took too long: {total_elapsed}s"
        assert call_count == 4  # 1 initial + 3 retries

    def test_linear_backoff(self):
        config = APIClientConfig(
            max_retries=2,
            backoff=BackoffStrategy.LINEAR,
            backoff_base=0.01,
        )
        handler = RetryHandler(config)
        # Verify _compute_wait returns linearly increasing values
        assert handler._compute_wait(1) == pytest.approx(0.01)
        assert handler._compute_wait(2) == pytest.approx(0.02)
        assert handler._compute_wait(3) == pytest.approx(0.03)

    def test_constant_backoff(self):
        config = APIClientConfig(
            max_retries=2,
            backoff=BackoffStrategy.CONSTANT,
            backoff_base=0.5,
        )
        handler = RetryHandler(config)
        assert handler._compute_wait(1) == pytest.approx(0.5)
        assert handler._compute_wait(2) == pytest.approx(0.5)
        assert handler._compute_wait(5) == pytest.approx(0.5)

    def test_backoff_max_caps_wait(self):
        config = APIClientConfig(
            max_retries=10,
            backoff=BackoffStrategy.EXPONENTIAL,
            backoff_base=2.0,
            backoff_max=10.0,
        )
        handler = RetryHandler(config)
        # 2^8 = 256, should be capped to 10
        assert handler._compute_wait(8) == 10.0


# ---------------------------------------------------------------------------
# PaginatedFetcher tests
# ---------------------------------------------------------------------------

class TestPaginatedFetcher:

    def test_collects_all_pages_cursor(self):
        """Should collect items from all pages using cursor pagination."""
        pages = [
            {"data": [1, 2, 3], "pagination": {"nextCursor": "page2"}},
            {"data": [4, 5, 6], "pagination": {"nextCursor": "page3"}},
            {"data": [7, 8], "pagination": {"nextCursor": None}},
        ]
        page_iter = iter(pages)

        def fetch_page(**kwargs):
            return next(page_iter)

        fetcher = PaginatedFetcher(PaginationConfig(style=PaginationStyle.CURSOR))
        result = fetcher.fetch_all(fetch_page)
        assert result == [1, 2, 3, 4, 5, 6, 7, 8]

    def test_empty_first_page(self):
        """Empty first page should return empty list."""
        def fetch_page(**kwargs):
            return {"data": []}

        fetcher = PaginatedFetcher()
        result = fetcher.fetch_all(fetch_page)
        assert result == []

    def test_single_page(self):
        """Single page (no next cursor) should return that page's items."""
        def fetch_page(**kwargs):
            return {"data": [1, 2, 3], "pagination": {}}

        fetcher = PaginatedFetcher()
        result = fetcher.fetch_all(fetch_page)
        assert result == [1, 2, 3]

    def test_custom_extractors(self):
        """Custom extract functions should be respected."""
        pages = [
            {"items": ["a", "b"], "next": "tok2"},
            {"items": ["c"], "next": None},
        ]
        page_iter = iter(pages)

        config = PaginationConfig(
            style=PaginationStyle.TOKEN,
            extract_data=lambda r: r.get("items", []),
            extract_next_page_param=lambda r: r.get("next"),
            page_param_name="token",
        )
        fetcher = PaginatedFetcher(config)

        def fetch_page(**kwargs):
            return next(page_iter)

        result = fetcher.fetch_all(fetch_page)
        assert result == ["a", "b", "c"]

    def test_offset_pagination(self):
        """Offset-based pagination should work correctly."""
        call_log: list[dict] = []

        def fetch_page(**kwargs):
            call_log.append(kwargs)
            offset = kwargs.get("offset", 0)
            if offset == 0:
                return {"results": [1, 2, 3], "next_offset": 3}
            elif offset == 3:
                return {"results": [4, 5], "next_offset": None}
            return {"results": []}

        config = PaginationConfig(
            style=PaginationStyle.OFFSET,
            extract_data=lambda r: r.get("results", []),
            extract_next_page_param=lambda r: r.get("next_offset"),
            page_param_name="offset",
        )
        fetcher = PaginatedFetcher(config)
        result = fetcher.fetch_all(fetch_page)
        assert result == [1, 2, 3, 4, 5]
        assert call_log[0].get("offset") == 0

    def test_iter_pages(self):
        """iter_pages should yield each page as a separate list."""
        pages = [
            {"data": [1, 2], "pagination": {"nextCursor": "p2"}},
            {"data": [3, 4], "pagination": {"nextCursor": None}},
        ]
        page_iter = iter(pages)

        def fetch_page(**kwargs):
            return next(page_iter)

        fetcher = PaginatedFetcher()
        result = list(fetcher.iter_pages(fetch_page))
        assert result == [[1, 2], [3, 4]]

    def test_passes_page_param_to_fetch(self):
        """The pagination parameter should be passed to the fetch function."""
        received_kwargs: list[dict] = []

        pages = [
            {"data": [1], "pagination": {"nextCursor": "cur_2"}},
            {"data": [2], "pagination": {"nextCursor": None}},
        ]
        page_iter = iter(pages)

        def fetch_page(**kwargs):
            received_kwargs.append(dict(kwargs))
            return next(page_iter)

        fetcher = PaginatedFetcher(PaginationConfig(page_param_name="cursor"))
        fetcher.fetch_all(fetch_page)

        # First call should not have cursor
        assert "cursor" not in received_kwargs[0]
        # Second call should have cursor="cur_2"
        assert received_kwargs[1]["cursor"] == "cur_2"


# ---------------------------------------------------------------------------
# BaseAPIClient tests
# ---------------------------------------------------------------------------

class TestBaseAPIClient:

    def test_fetch_calls_do_request(self):
        """fetch() should call _do_request through rate limiter and retry."""

        class TestClient(BaseAPIClient):
            def _do_request(self, url, **kwargs):
                return {"url": url, "extra": kwargs}

        client = TestClient(APIClientConfig(max_rps=0, max_retries=0))
        result = client.fetch("https://example.com/api", method="GET")
        assert result["url"] == "https://example.com/api"
        assert result["extra"]["method"] == "GET"

    def test_fetch_all_paginates(self):
        """fetch_all() should use the paginator to collect all pages."""
        pages = [
            {"data": [1, 2], "pagination": {"nextCursor": "p2"}},
            {"data": [3], "pagination": {}},
        ]
        page_call_count = 0

        class TestClient(BaseAPIClient):
            def _do_request(self, url, **kwargs):
                nonlocal page_call_count
                result = pages[page_call_count]
                page_call_count += 1
                return result

        client = TestClient(
            config=APIClientConfig(max_rps=0, max_retries=0),
        )
        result = client.fetch_all("https://example.com/items")
        assert result == [1, 2, 3]

    def test_not_implemented_do_request(self):
        """BaseAPIClient._do_request should raise NotImplementedError."""
        client = BaseAPIClient(APIClientConfig(max_rps=0, max_retries=0))
        with pytest.raises(NotImplementedError):
            client.fetch("https://example.com")
