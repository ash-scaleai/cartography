"""
Shared API client framework for Cartography.

Provides reusable rate-limiting, retry with backoff, and pagination helpers
so that individual provider modules do not need to duplicate this logic.

Design principles:
- Declarative configuration via APIClientConfig
- Rate limiter is per-client-instance (each provider gets its own)
- Thread-safe (safe with concurrent.futures / asyncio.to_thread)
- Opt-in: existing modules continue working; new/migrated modules use the shared client
- Neo4j retry stays separate (different failure modes)
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from typing import Any
from typing import Callable
from typing import Generic
from typing import Iterator
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class BackoffStrategy(Enum):
    """Supported backoff strategies for retries."""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CONSTANT = "constant"


@dataclass(frozen=True)
class APIClientConfig:
    """
    Declarative configuration for an API client.

    Example::

        config = APIClientConfig(
            max_rps=10,
            retry_on=[429, 503],
            backoff=BackoffStrategy.EXPONENTIAL,
            max_retries=5,
            timeout=60,
        )
    """
    max_rps: float = 0
    """Maximum requests per second. 0 means unlimited."""

    retry_on: tuple[int, ...] = (429, 500, 502, 503, 504)
    """HTTP status codes that trigger a retry."""

    backoff: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    """Backoff strategy between retries."""

    max_retries: int = 5
    """Maximum number of retry attempts (not counting the initial request)."""

    timeout: float = 60
    """Per-request timeout in seconds."""

    backoff_base: float = 2.0
    """Base multiplier for backoff calculation."""

    backoff_max: float = 120.0
    """Maximum backoff wait time in seconds."""


# ---------------------------------------------------------------------------
# Rate Limiter  (token-bucket algorithm, thread-safe)
# ---------------------------------------------------------------------------

class RateLimiter:
    """
    Token-bucket rate limiter.

    Each call to :meth:`acquire` consumes one token.  Tokens are replenished
    at ``max_rps`` tokens per second.  If no tokens are available the caller
    blocks until one becomes available.

    The implementation is thread-safe so it can be shared across threads
    (e.g. when using ``concurrent.futures.ThreadPoolExecutor``).
    """

    def __init__(self, max_rps: float) -> None:
        if max_rps < 0:
            raise ValueError(f"max_rps must be >= 0, got {max_rps}")
        self._max_rps = max_rps
        self._lock = threading.Lock()
        # Start with a full bucket of 1 token so the first request goes through
        # immediately.
        self._tokens: float = 1.0 if max_rps > 0 else 0.0
        self._max_tokens: float = max(1.0, max_rps)  # burst allowance = 1s worth
        self._last_refill: float = time.monotonic()

    @property
    def max_rps(self) -> float:
        return self._max_rps

    def _refill(self) -> None:
        """Add tokens based on elapsed time since last refill."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed > 0:
            self._tokens = min(
                self._max_tokens,
                self._tokens + elapsed * self._max_rps,
            )
            self._last_refill = now

    def acquire(self) -> float:
        """
        Block until a token is available, then consume it.

        Returns the number of seconds the caller was blocked (0 if a token was
        immediately available).
        """
        if self._max_rps <= 0:
            return 0.0

        total_wait = 0.0
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return total_wait
                # Calculate how long until the next token arrives
                deficit = 1.0 - self._tokens
                wait = deficit / self._max_rps

            # Sleep outside the lock so other threads can proceed
            time.sleep(wait)
            total_wait += wait


# ---------------------------------------------------------------------------
# Retry Handler
# ---------------------------------------------------------------------------

class RetryHandler:
    """
    Configurable retry handler with pluggable backoff strategies.

    Given a callable that may raise exceptions, :meth:`execute` will retry the
    call according to the configured strategy and limits.
    """

    def __init__(self, config: APIClientConfig) -> None:
        self._config = config

    @property
    def config(self) -> APIClientConfig:
        return self._config

    def _compute_wait(self, attempt: int) -> float:
        """Return the wait time (seconds) before the given retry attempt."""
        cfg = self._config
        if cfg.backoff is BackoffStrategy.EXPONENTIAL:
            wait = cfg.backoff_base ** attempt
        elif cfg.backoff is BackoffStrategy.LINEAR:
            wait = cfg.backoff_base * attempt
        elif cfg.backoff is BackoffStrategy.CONSTANT:
            wait = cfg.backoff_base
        else:
            wait = cfg.backoff_base ** attempt
        return min(wait, cfg.backoff_max)

    def should_retry(self, attempt: int, exc: Exception) -> bool:
        """
        Decide whether to retry based on the exception and attempt number.

        Override in subclasses to add provider-specific giveup logic.
        """
        return attempt < self._config.max_retries

    def execute(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """
        Call *func* with retry logic.

        :raises: The last exception if all retries are exhausted.
        """
        last_exc: Exception | None = None
        for attempt in range(self._config.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                if not self.should_retry(attempt, exc):
                    raise
                if attempt < self._config.max_retries:
                    wait = self._compute_wait(attempt + 1)
                    logger.warning(
                        "Retry attempt %d/%d after error: %s. "
                        "Waiting %.1fs before next attempt.",
                        attempt + 1,
                        self._config.max_retries,
                        exc,
                        wait,
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        "All %d retries exhausted. Last error: %s",
                        self._config.max_retries,
                        exc,
                    )
                    raise
        # Should not be reached, but satisfy the type checker
        assert last_exc is not None  # pragma: no cover
        raise last_exc  # pragma: no cover


# ---------------------------------------------------------------------------
# Paginated Fetcher
# ---------------------------------------------------------------------------

class PaginationStyle(Enum):
    """Supported pagination styles."""
    CURSOR = "cursor"
    TOKEN = "token"  # same as cursor but uses a different field name convention
    OFFSET = "offset"
    LINK_HEADER = "link_header"


@dataclass
class PaginationConfig:
    """
    Configuration for pagination.

    Callers provide callables that extract the page data and the next-page
    indicator from a raw response.
    """
    style: PaginationStyle = PaginationStyle.CURSOR

    extract_data: Callable[[Any], list[Any]] = field(
        default_factory=lambda: _default_extract_data,
    )
    """Callable that extracts items from a response object."""

    extract_next_page_param: Callable[[Any], str | int | None] = field(
        default_factory=lambda: _default_extract_next_page_param,
    )
    """Callable that extracts the next-page cursor/offset/token from a response. Returns None when done."""

    page_param_name: str = "cursor"
    """The query parameter or body field name for the next-page indicator."""

    page_size: int = 100
    """Number of items per page."""


def _default_extract_data(response: Any) -> list[Any]:
    """Default data extractor: assume response is a dict with a 'data' key."""
    if isinstance(response, dict):
        return response.get("data", [])
    if isinstance(response, list):
        return response
    return []


def _default_extract_next_page_param(response: Any) -> str | int | None:
    """Default next-page extractor: look for pagination.nextCursor or next_cursor."""
    if not isinstance(response, dict):
        return None
    # Try common pagination structures
    pagination = response.get("pagination", {})
    if isinstance(pagination, dict):
        cursor = pagination.get("nextCursor") or pagination.get("next_cursor")
        if cursor:
            return cursor
    # Try top-level pageInfo (GitHub GraphQL style)
    page_info = response.get("pageInfo", {})
    if isinstance(page_info, dict):
        if page_info.get("hasNextPage"):
            return page_info.get("endCursor")
    return None


class PaginatedFetcher(Generic[T]):
    """
    Generic pagination helper.

    Wraps a single-page fetch function and collects all pages automatically.
    Works with cursor-based, token-based, and offset-based pagination.
    """

    def __init__(self, pagination_config: PaginationConfig | None = None) -> None:
        self._config = pagination_config or PaginationConfig()

    @property
    def config(self) -> PaginationConfig:
        return self._config

    def fetch_all(
        self,
        fetch_page_func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> list[T]:
        """
        Fetch all pages by repeatedly calling *fetch_page_func*.

        The fetch function receives an extra keyword argument named after
        ``config.page_param_name`` with the current page indicator value.

        :returns: A flat list of all items across all pages.
        """
        all_items: list[T] = []
        page_param: str | int | None = None

        while True:
            # Inject the pagination parameter
            call_kwargs = dict(kwargs)
            if page_param is not None:
                call_kwargs[self._config.page_param_name] = page_param
            elif self._config.style is PaginationStyle.OFFSET:
                call_kwargs[self._config.page_param_name] = 0

            response = fetch_page_func(*args, **call_kwargs)

            items = self._config.extract_data(response)
            all_items.extend(items)

            if not items:
                break

            next_param = self._config.extract_next_page_param(response)
            if next_param is None:
                break

            if self._config.style is PaginationStyle.OFFSET:
                # For offset-based, the extract_next_page_param should return the new offset
                page_param = next_param
            else:
                page_param = next_param

        return all_items

    def iter_pages(
        self,
        fetch_page_func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Iterator[list[T]]:
        """
        Yield each page of items as a list.

        Useful when callers want to process pages incrementally rather than
        collecting everything in memory.
        """
        page_param: str | int | None = None

        while True:
            call_kwargs = dict(kwargs)
            if page_param is not None:
                call_kwargs[self._config.page_param_name] = page_param
            elif self._config.style is PaginationStyle.OFFSET:
                call_kwargs[self._config.page_param_name] = 0

            response = fetch_page_func(*args, **call_kwargs)

            items = self._config.extract_data(response)
            if not items:
                break

            yield items

            next_param = self._config.extract_next_page_param(response)
            if next_param is None:
                break

            page_param = next_param


# ---------------------------------------------------------------------------
# Base API Client
# ---------------------------------------------------------------------------

class BaseAPIClient:
    """
    Base API client combining rate limiting, retry, and pagination.

    Provider-specific clients should subclass this and override
    :meth:`_do_request` with the actual HTTP/SDK call.

    Example subclass usage::

        class MyClient(BaseAPIClient):
            def _do_request(self, url, **kwargs):
                return requests.get(url, timeout=self.config.timeout)

        client = MyClient(APIClientConfig(max_rps=10, retry_on=[429, 503]))
        data = client.fetch("https://api.example.com/items")
    """

    def __init__(
        self,
        config: APIClientConfig | None = None,
        pagination_config: PaginationConfig | None = None,
    ) -> None:
        self._config = config or APIClientConfig()
        self._rate_limiter = RateLimiter(self._config.max_rps)
        self._retry_handler = RetryHandler(self._config)
        self._paginator = PaginatedFetcher(pagination_config)

    @property
    def config(self) -> APIClientConfig:
        return self._config

    @property
    def rate_limiter(self) -> RateLimiter:
        return self._rate_limiter

    @property
    def retry_handler(self) -> RetryHandler:
        return self._retry_handler

    def _do_request(self, url: str, **kwargs: Any) -> Any:
        """
        Perform the actual request. Subclasses must implement this.

        :param url: The URL or endpoint to call.
        :param kwargs: Additional arguments (headers, params, etc.).
        :returns: The response (parsed or raw).
        :raises: An exception on failure (will be caught by retry logic).
        """
        raise NotImplementedError(
            "Subclasses must implement _do_request",
        )

    def fetch(self, url: str, **kwargs: Any) -> Any:
        """
        Perform a single request with rate limiting and retry.

        :param url: The URL or endpoint to call.
        :param kwargs: Additional arguments forwarded to ``_do_request``.
        :returns: The response from ``_do_request``.
        """
        def _rate_limited_request() -> Any:
            wait = self._rate_limiter.acquire()
            if wait > 0:
                logger.info(
                    "Rate limited, waited %.1fs before request to %s",
                    wait,
                    url,
                )
            return self._do_request(url, **kwargs)

        return self._retry_handler.execute(_rate_limited_request)

    def fetch_all(self, url: str, **kwargs: Any) -> list[Any]:
        """
        Fetch all pages from a paginated endpoint.

        Uses the configured :class:`PaginatedFetcher` to iterate through pages,
        applying rate limiting and retry on each page request.

        :param url: The URL or endpoint to call.
        :param kwargs: Additional arguments forwarded to ``fetch``.
        :returns: A flat list of all items across all pages.
        """
        return self._paginator.fetch_all(self.fetch, url, **kwargs)
