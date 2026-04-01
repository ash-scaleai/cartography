"""
AWS-specific client wrapping boto3 with shared retry and rate-limit config.

This module provides an :class:`AWSClient` that combines the shared
:class:`~cartography.client.base.RateLimiter` and
:class:`~cartography.client.base.RetryHandler` with boto3's own retry
configuration for a consistent experience.

Design notes:
- boto3 has its own retry mechanism (via botocore). This client adds an
  *outer* rate limiter so that Cartography can respect AWS service-level
  rate limits (e.g. EC2 Describe* calls at 20 rps).
- The retry handler here catches *botocore* ``ClientError`` with throttling
  codes and lets other errors propagate.
- The existing ``cartography.intel.aws.util.botocore_config`` helpers remain
  the canonical way to create raw boto3 clients. This module provides an
  optional higher-level wrapper.
"""
from __future__ import annotations

import logging
from typing import Any

import botocore.config
import botocore.exceptions

from cartography.client.base import APIClientConfig
from cartography.client.base import BackoffStrategy
from cartography.client.base import BaseAPIClient
from cartography.client.base import PaginationConfig
from cartography.client.base import RetryHandler

logger = logging.getLogger(__name__)

# AWS throttling error codes that warrant a retry
_THROTTLING_ERROR_CODES = frozenset({
    "Throttling",
    "ThrottlingException",
    "ThrottledException",
    "RequestThrottledException",
    "TooManyRequestsException",
    "ProvisionedThroughputExceededException",
    "TransactionInProgressException",
    "RequestLimitExceeded",
    "BandwidthLimitExceeded",
    "LimitExceededException",
    "RequestThrottled",
    "SlowDown",
    "EC2ThrottledException",
})


def default_aws_config() -> APIClientConfig:
    """Return a sensible default :class:`APIClientConfig` for AWS APIs."""
    return APIClientConfig(
        max_rps=0,  # rely on botocore's adaptive retry by default
        retry_on=(),  # not HTTP-based; we use error code matching instead
        backoff=BackoffStrategy.EXPONENTIAL,
        max_retries=5,
        timeout=120,
        backoff_base=2.0,
        backoff_max=60.0,
    )


class AWSRetryHandler(RetryHandler):
    """
    Retry handler that understands botocore ``ClientError`` throttling codes.
    """

    def should_retry(self, attempt: int, exc: Exception) -> bool:
        if attempt >= self.config.max_retries:
            return False

        if isinstance(exc, botocore.exceptions.ClientError):
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in _THROTTLING_ERROR_CODES:
                return True

        # Retry on endpoint connection errors (transient network issues)
        if isinstance(exc, botocore.exceptions.EndpointConnectionError):
            return True

        # Retry on connection-closed errors
        if isinstance(exc, botocore.exceptions.ConnectionClosedError):
            return True

        return False


class AWSClient(BaseAPIClient):
    """
    AWS API client wrapping a boto3 client with shared rate limiting and retry.

    Example::

        import boto3
        session = boto3.Session()
        ec2_boto = session.client("ec2", region_name="us-east-1")

        client = AWSClient(
            boto3_client=ec2_boto,
            config=APIClientConfig(max_rps=20),  # EC2 Describe* limit
        )
        result = client.call("describe_instances", Filters=[...])

        # Paginated call
        all_instances = client.call_paginated(
            "describe_instances",
            pagination_token_field="NextToken",
            result_key="Reservations",
        )
    """

    def __init__(
        self,
        boto3_client: Any,
        config: APIClientConfig | None = None,
        pagination_config: PaginationConfig | None = None,
    ) -> None:
        resolved_config = config or default_aws_config()
        super().__init__(config=resolved_config, pagination_config=pagination_config)
        self._boto3_client = boto3_client
        # Replace the default retry handler with AWS-aware one
        self._retry_handler = AWSRetryHandler(self._config)

    @property
    def boto3_client(self) -> Any:
        return self._boto3_client

    def _do_request(self, url: str, **kwargs: Any) -> Any:
        """
        For AWSClient, ``url`` is the boto3 API method name.

        :param url: The boto3 method name (e.g. "describe_instances").
        :param kwargs: Arguments to pass to the boto3 method.
        """
        method = getattr(self._boto3_client, url)
        return method(**kwargs)

    def call(self, method_name: str, **kwargs: Any) -> Any:
        """
        Call a boto3 API method with rate limiting and retry.

        :param method_name: The boto3 method name (e.g. "describe_instances").
        :param kwargs: Arguments to pass to the boto3 method.
        :returns: The boto3 response dict.
        """
        return self.fetch(method_name, **kwargs)

    def call_paginated(
        self,
        method_name: str,
        *,
        pagination_token_field: str = "NextToken",
        pagination_request_field: str | None = None,
        result_key: str,
        **kwargs: Any,
    ) -> list[Any]:
        """
        Call a boto3 API method with automatic pagination.

        Many AWS APIs use a ``NextToken`` pattern. This method repeatedly calls
        the API until no more pages are available.

        :param method_name: The boto3 method name.
        :param pagination_token_field: Response field containing the next page token.
        :param pagination_request_field: Request field for the page token. Defaults
            to the same name as *pagination_token_field*.
        :param result_key: Response field containing the list of items.
        :param kwargs: Additional arguments forwarded to the boto3 method.
        :returns: A flat list of all items across all pages.
        """
        request_field = pagination_request_field or pagination_token_field
        all_items: list[Any] = []
        next_token: str | None = None

        while True:
            call_kwargs = dict(kwargs)
            if next_token is not None:
                call_kwargs[request_field] = next_token

            response = self.call(method_name, **call_kwargs)

            items = response.get(result_key, [])
            all_items.extend(items)

            next_token = response.get(pagination_token_field)
            if not next_token:
                break

        return all_items
