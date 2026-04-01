"""Tests for cartography.client.aws — AWS client with retry and rate limiting."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cartography.client.aws.boto3_client import AWSClient
from cartography.client.aws.boto3_client import AWSRetryHandler
from cartography.client.aws.boto3_client import default_aws_config
from cartography.client.base import APIClientConfig
from cartography.client.base import BackoffStrategy

# We test against botocore exception types but don't require a real AWS
# connection.  Import conditionally.
try:
    import botocore.exceptions
    HAS_BOTOCORE = True
except ImportError:
    HAS_BOTOCORE = False

pytestmark = pytest.mark.skipif(not HAS_BOTOCORE, reason="botocore not installed")


class TestAWSRetryHandler:

    def test_retries_on_throttling(self):
        config = default_aws_config()
        handler = AWSRetryHandler(config)

        exc = botocore.exceptions.ClientError(
            {"Error": {"Code": "Throttling", "Message": "Rate exceeded"}},
            "DescribeInstances",
        )
        assert handler.should_retry(0, exc) is True
        assert handler.should_retry(4, exc) is True
        # After max_retries, give up
        assert handler.should_retry(5, exc) is False

    def test_retries_on_too_many_requests(self):
        config = default_aws_config()
        handler = AWSRetryHandler(config)

        exc = botocore.exceptions.ClientError(
            {"Error": {"Code": "TooManyRequestsException", "Message": "slow down"}},
            "SomeApi",
        )
        assert handler.should_retry(0, exc) is True

    def test_no_retry_on_access_denied(self):
        config = default_aws_config()
        handler = AWSRetryHandler(config)

        exc = botocore.exceptions.ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "no access"}},
            "SomeApi",
        )
        assert handler.should_retry(0, exc) is False

    def test_retries_on_endpoint_connection_error(self):
        config = default_aws_config()
        handler = AWSRetryHandler(config)

        exc = botocore.exceptions.EndpointConnectionError(endpoint_url="https://ec2.us-east-1.amazonaws.com")
        assert handler.should_retry(0, exc) is True

    def test_no_retry_on_value_error(self):
        config = default_aws_config()
        handler = AWSRetryHandler(config)

        exc = ValueError("bad input")
        assert handler.should_retry(0, exc) is False


class TestAWSClient:

    def test_call_delegates_to_boto3(self):
        """call() should invoke the named method on the boto3 client."""
        mock_boto = MagicMock()
        mock_boto.describe_instances.return_value = {
            "Reservations": [{"InstanceId": "i-123"}],
        }

        client = AWSClient(
            boto3_client=mock_boto,
            config=APIClientConfig(max_rps=0, max_retries=0),
        )

        result = client.call("describe_instances", Filters=[])
        assert result["Reservations"][0]["InstanceId"] == "i-123"
        mock_boto.describe_instances.assert_called_once_with(Filters=[])

    def test_call_paginated_collects_all_pages(self):
        """call_paginated() should collect items across multiple pages."""
        mock_boto = MagicMock()
        call_count = 0

        def mock_list_objects(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "Contents": [{"Key": "file1"}, {"Key": "file2"}],
                    "NextToken": "tok2",
                }
            else:
                return {
                    "Contents": [{"Key": "file3"}],
                }

        mock_boto.list_objects = mock_list_objects

        client = AWSClient(
            boto3_client=mock_boto,
            config=APIClientConfig(max_rps=0, max_retries=0),
        )

        result = client.call_paginated(
            "list_objects",
            pagination_token_field="NextToken",
            result_key="Contents",
        )
        assert len(result) == 3
        assert result[0]["Key"] == "file1"
        assert result[2]["Key"] == "file3"

    def test_call_retries_throttling(self):
        """call() should retry on throttling and return on success."""
        mock_boto = MagicMock()
        call_count = 0

        def mock_api(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise botocore.exceptions.ClientError(
                    {"Error": {"Code": "Throttling", "Message": "Rate exceeded"}},
                    "DescribeInstances",
                )
            return {"data": "ok"}

        mock_boto.describe_instances = mock_api

        client = AWSClient(
            boto3_client=mock_boto,
            config=APIClientConfig(
                max_rps=0,
                max_retries=5,
                backoff=BackoffStrategy.CONSTANT,
                backoff_base=0.01,
            ),
        )

        result = client.call("describe_instances")
        assert result == {"data": "ok"}
        assert call_count == 3
