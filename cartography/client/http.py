"""
Generic HTTP client for REST APIs (GitHub, Okta, SentinelOne, etc.).

Wraps the ``requests`` library with the shared rate-limiting, retry, and
pagination framework from :mod:`cartography.client.base`.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from cartography.client.base import APIClientConfig
from cartography.client.base import BaseAPIClient
from cartography.client.base import PaginationConfig
from cartography.client.base import RetryHandler

logger = logging.getLogger(__name__)


class HTTPRetryHandler(RetryHandler):
    """
    Retry handler that understands HTTP status codes.

    Retries are triggered when a :class:`requests.exceptions.HTTPError` has a
    status code listed in ``config.retry_on``, or for transient network errors
    (timeouts, connection errors).
    """

    _TRANSIENT_EXCEPTIONS = (
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
        requests.exceptions.ChunkedEncodingError,
    )

    def should_retry(self, attempt: int, exc: Exception) -> bool:
        if attempt >= self.config.max_retries:
            return False

        # Always retry transient network errors
        if isinstance(exc, self._TRANSIENT_EXCEPTIONS):
            return True

        # Retry specific HTTP status codes
        if isinstance(exc, requests.exceptions.HTTPError):
            response = exc.response
            if response is not None and response.status_code in self.config.retry_on:
                return True

        return False


class HTTPClient(BaseAPIClient):
    """
    Generic HTTP client for REST APIs.

    Example::

        client = HTTPClient(
            config=APIClientConfig(max_rps=10, retry_on=(429, 503)),
            base_url="https://api.example.com",
            default_headers={"Authorization": "Bearer TOKEN"},
        )
        data = client.fetch("/users")
        all_users = client.fetch_all("/users")
    """

    def __init__(
        self,
        config: APIClientConfig | None = None,
        pagination_config: PaginationConfig | None = None,
        base_url: str = "",
        default_headers: dict[str, str] | None = None,
        session: requests.Session | None = None,
    ) -> None:
        super().__init__(config=config, pagination_config=pagination_config)
        self._base_url = base_url.rstrip("/")
        self._default_headers = default_headers or {}
        self._session = session or requests.Session()
        # Replace the default retry handler with HTTP-aware one
        self._retry_handler = HTTPRetryHandler(self._config)

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def session(self) -> requests.Session:
        return self._session

    def _build_url(self, endpoint: str) -> str:
        """Build the full URL from base_url and endpoint."""
        if endpoint.startswith(("http://", "https://")):
            return endpoint
        return f"{self._base_url}/{endpoint.lstrip('/')}"

    def _do_request(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: Any = None,
        data: Any = None,
        **kwargs: Any,
    ) -> Any:
        """
        Perform an HTTP request and return the parsed JSON response.

        :raises requests.exceptions.HTTPError: On non-2xx response.
        :raises requests.exceptions.Timeout: On timeout.
        :raises requests.exceptions.ConnectionError: On connection failure.
        """
        full_url = self._build_url(url)
        merged_headers = {**self._default_headers}
        if headers:
            merged_headers.update(headers)

        response = self._session.request(
            method=method,
            url=full_url,
            headers=merged_headers,
            params=params,
            json=json,
            data=data,
            timeout=self._config.timeout,
            **kwargs,
        )
        response.raise_for_status()
        return response.json()

    def fetch(self, url: str, **kwargs: Any) -> Any:
        """
        Perform a single HTTP request with rate limiting and retry.

        Accepts all keyword arguments supported by :meth:`_do_request`
        (method, headers, params, json, data).
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

    def fetch_raw(self, url: str, **kwargs: Any) -> requests.Response:
        """
        Perform a request and return the raw :class:`requests.Response`.

        Useful when callers need access to headers (e.g. for Link-header
        pagination or rate-limit headers).
        """
        full_url = self._build_url(url)
        merged_headers = {**self._default_headers}
        if "headers" in kwargs:
            merged_headers.update(kwargs.pop("headers"))

        method = kwargs.pop("method", "GET")

        def _do() -> requests.Response:
            wait = self._rate_limiter.acquire()
            if wait > 0:
                logger.info(
                    "Rate limited, waited %.1fs before request to %s",
                    wait,
                    url,
                )
            resp = self._session.request(
                method=method,
                url=full_url,
                headers=merged_headers,
                timeout=self._config.timeout,
                **kwargs,
            )
            resp.raise_for_status()
            return resp

        return self._retry_handler.execute(_do)
