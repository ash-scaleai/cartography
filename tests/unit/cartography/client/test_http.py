"""Tests for cartography.client.http — HTTP client with retry and rate limiting."""
from __future__ import annotations

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
import requests

from cartography.client.base import APIClientConfig
from cartography.client.base import BackoffStrategy
from cartography.client.http import HTTPClient
from cartography.client.http import HTTPRetryHandler


class TestHTTPRetryHandler:

    def test_retries_on_429(self):
        """Should retry on HTTP 429 (Too Many Requests)."""
        config = APIClientConfig(retry_on=(429, 503), max_retries=3)
        handler = HTTPRetryHandler(config)

        response = MagicMock()
        response.status_code = 429
        exc = requests.exceptions.HTTPError(response=response)

        assert handler.should_retry(0, exc) is True
        assert handler.should_retry(1, exc) is True
        assert handler.should_retry(2, exc) is True
        # After max_retries, give up
        assert handler.should_retry(3, exc) is False

    def test_retries_on_503(self):
        """Should retry on HTTP 503 (Service Unavailable)."""
        config = APIClientConfig(retry_on=(429, 503), max_retries=3)
        handler = HTTPRetryHandler(config)

        response = MagicMock()
        response.status_code = 503
        exc = requests.exceptions.HTTPError(response=response)

        assert handler.should_retry(0, exc) is True

    def test_no_retry_on_404(self):
        """Should not retry on HTTP 404."""
        config = APIClientConfig(retry_on=(429, 503), max_retries=3)
        handler = HTTPRetryHandler(config)

        response = MagicMock()
        response.status_code = 404
        exc = requests.exceptions.HTTPError(response=response)

        assert handler.should_retry(0, exc) is False

    def test_retries_on_timeout(self):
        """Should retry on Timeout exceptions."""
        config = APIClientConfig(max_retries=3)
        handler = HTTPRetryHandler(config)

        exc = requests.exceptions.Timeout("timed out")
        assert handler.should_retry(0, exc) is True

    def test_retries_on_connection_error(self):
        """Should retry on ConnectionError."""
        config = APIClientConfig(max_retries=3)
        handler = HTTPRetryHandler(config)

        exc = requests.exceptions.ConnectionError("connection refused")
        assert handler.should_retry(0, exc) is True

    def test_no_retry_on_value_error(self):
        """Should not retry on non-HTTP exceptions."""
        config = APIClientConfig(max_retries=3)
        handler = HTTPRetryHandler(config)

        exc = ValueError("bad value")
        assert handler.should_retry(0, exc) is False


class TestHTTPClient:

    def test_fetch_with_mock_429_then_success(self):
        """
        Should retry on 429 and eventually return successful response.
        """
        config = APIClientConfig(
            max_rps=0,
            retry_on=(429,),
            max_retries=3,
            backoff=BackoffStrategy.CONSTANT,
            backoff_base=0.01,
        )

        mock_session = MagicMock()
        call_count = 0

        def mock_request(**kwargs):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            if call_count < 3:
                resp.status_code = 429
                resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
                    response=resp,
                )
            else:
                resp.status_code = 200
                resp.json.return_value = {"result": "ok"}
                resp.raise_for_status.return_value = None
            return resp

        mock_session.request = mock_request

        client = HTTPClient(
            config=config,
            base_url="https://api.example.com",
            session=mock_session,
        )

        result = client.fetch("/test")
        assert result == {"result": "ok"}
        assert call_count == 3

    def test_fetch_gives_up_after_max_retries(self):
        """Should raise after exhausting all retries."""
        config = APIClientConfig(
            max_rps=0,
            retry_on=(500,),
            max_retries=2,
            backoff=BackoffStrategy.CONSTANT,
            backoff_base=0.01,
        )

        mock_session = MagicMock()

        def mock_request(**kwargs):
            resp = MagicMock()
            resp.status_code = 500
            resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
                response=resp,
            )
            return resp

        mock_session.request = mock_request

        client = HTTPClient(
            config=config,
            base_url="https://api.example.com",
            session=mock_session,
        )

        with pytest.raises(requests.exceptions.HTTPError):
            client.fetch("/test")

    def test_base_url_and_endpoint_joining(self):
        """Should correctly join base URL and endpoint paths."""
        mock_session = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {}
        resp.raise_for_status.return_value = None
        mock_session.request.return_value = resp

        client = HTTPClient(
            config=APIClientConfig(max_rps=0, max_retries=0),
            base_url="https://api.example.com/v1",
            session=mock_session,
        )

        client.fetch("/users")
        _, kwargs = mock_session.request.call_args
        assert kwargs["url"] == "https://api.example.com/v1/users"

    def test_absolute_url_bypasses_base(self):
        """Absolute URLs should not be prefixed with base_url."""
        mock_session = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {}
        resp.raise_for_status.return_value = None
        mock_session.request.return_value = resp

        client = HTTPClient(
            config=APIClientConfig(max_rps=0, max_retries=0),
            base_url="https://api.example.com",
            session=mock_session,
        )

        client.fetch("https://other.example.com/data")
        _, kwargs = mock_session.request.call_args
        assert kwargs["url"] == "https://other.example.com/data"

    def test_default_headers_merged(self):
        """Default headers should be included in every request."""
        mock_session = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {}
        resp.raise_for_status.return_value = None
        mock_session.request.return_value = resp

        client = HTTPClient(
            config=APIClientConfig(max_rps=0, max_retries=0),
            default_headers={"Authorization": "Bearer test-token"},
            session=mock_session,
        )

        client.fetch("https://api.example.com/data")
        _, kwargs = mock_session.request.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer test-token"
