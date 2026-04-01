import pytest

from cartography.events.models import CloudEvent
from cartography.events.sources.cloudtrail import CloudTrailEventSource
from cartography.events.sources.cloudtrail import parse_cloudtrail_event


class TestParseCloudtrailEvent:
    def test_parse_basic_event(self) -> None:
        raw = {
            "eventName": "RunInstances",
            "awsRegion": "us-east-1",
            "recipientAccountId": "123456789012",
            "eventTime": "2023-11-14T12:00:00Z",
        }
        event = parse_cloudtrail_event(raw)
        assert event is not None
        assert event.source == "aws.cloudtrail"
        assert event.event_type == "RunInstances"
        assert event.region == "us-east-1"
        assert event.account_id == "123456789012"
        assert event.timestamp == 1699963200
        assert event.raw_data is raw

    def test_parse_event_with_resource_id_from_response(self) -> None:
        raw = {
            "eventName": "RunInstances",
            "awsRegion": "us-west-2",
            "recipientAccountId": "123456789012",
            "eventTime": "2023-11-14T12:00:00Z",
            "responseElements": {
                "instancesSet": {
                    "items": [
                        {"instanceId": "i-abc123"},
                    ],
                },
            },
        }
        event = parse_cloudtrail_event(raw)
        assert event is not None
        assert event.resource_id == "i-abc123"

    def test_parse_event_with_resource_id_from_request_params(self) -> None:
        raw = {
            "eventName": "TerminateInstances",
            "awsRegion": "us-east-1",
            "recipientAccountId": "123456789012",
            "eventTime": "2023-11-14T12:00:00Z",
            "requestParameters": {
                "instanceId": "i-xyz789",
            },
        }
        event = parse_cloudtrail_event(raw)
        assert event is not None
        assert event.resource_id == "i-xyz789"

    def test_parse_event_with_bucket_name(self) -> None:
        raw = {
            "eventName": "CreateBucket",
            "awsRegion": "us-east-1",
            "recipientAccountId": "123456789012",
            "eventTime": "2023-11-14T12:00:00Z",
            "requestParameters": {
                "bucketName": "my-bucket",
            },
        }
        event = parse_cloudtrail_event(raw)
        assert event is not None
        assert event.resource_id == "my-bucket"

    def test_parse_event_missing_event_name(self) -> None:
        raw = {
            "awsRegion": "us-east-1",
            "recipientAccountId": "123456789012",
            "eventTime": "2023-11-14T12:00:00Z",
        }
        event = parse_cloudtrail_event(raw)
        assert event is None

    def test_parse_event_missing_region(self) -> None:
        raw = {
            "eventName": "RunInstances",
            "recipientAccountId": "123456789012",
            "eventTime": "2023-11-14T12:00:00Z",
        }
        event = parse_cloudtrail_event(raw)
        assert event is None

    def test_parse_event_missing_account_id(self) -> None:
        raw = {
            "eventName": "RunInstances",
            "awsRegion": "us-east-1",
            "eventTime": "2023-11-14T12:00:00Z",
        }
        event = parse_cloudtrail_event(raw)
        assert event is None

    def test_parse_event_missing_event_time(self) -> None:
        raw = {
            "eventName": "RunInstances",
            "awsRegion": "us-east-1",
            "recipientAccountId": "123456789012",
        }
        event = parse_cloudtrail_event(raw)
        assert event is None

    def test_parse_event_invalid_event_time(self) -> None:
        raw = {
            "eventName": "RunInstances",
            "awsRegion": "us-east-1",
            "recipientAccountId": "123456789012",
            "eventTime": "not-a-date",
        }
        event = parse_cloudtrail_event(raw)
        assert event is None

    def test_parse_event_account_from_user_identity(self) -> None:
        """Falls back to userIdentity.accountId if recipientAccountId missing."""
        raw = {
            "eventName": "RunInstances",
            "awsRegion": "us-east-1",
            "userIdentity": {"accountId": "999888777666"},
            "eventTime": "2023-11-14T12:00:00Z",
        }
        event = parse_cloudtrail_event(raw)
        assert event is not None
        assert event.account_id == "999888777666"

    def test_region_preserved_from_event(self) -> None:
        raw = {
            "eventName": "CreateBucket",
            "awsRegion": "ap-southeast-1",
            "recipientAccountId": "123456789012",
            "eventTime": "2023-11-14T12:00:00Z",
        }
        event = parse_cloudtrail_event(raw)
        assert event is not None
        assert event.region == "ap-southeast-1"


class TestCloudTrailEventSource:
    def test_parse_events_filters_invalid(self) -> None:
        source = CloudTrailEventSource()
        raw_events = [
            {
                "eventName": "RunInstances",
                "awsRegion": "us-east-1",
                "recipientAccountId": "123456789012",
                "eventTime": "2023-11-14T12:00:00Z",
            },
            {
                # Missing eventName - should be filtered out
                "awsRegion": "us-east-1",
                "recipientAccountId": "123456789012",
                "eventTime": "2023-11-14T12:00:00Z",
            },
            {
                "eventName": "CreateBucket",
                "awsRegion": "us-west-2",
                "recipientAccountId": "123456789012",
                "eventTime": "2023-11-14T13:00:00Z",
            },
        ]
        events = source.parse_events(raw_events)
        assert len(events) == 2
        assert events[0].event_type == "RunInstances"
        assert events[1].event_type == "CreateBucket"

    def test_parse_events_empty_list(self) -> None:
        source = CloudTrailEventSource()
        events = source.parse_events([])
        assert events == []

    def test_poll_without_session_raises(self) -> None:
        source = CloudTrailEventSource()
        with pytest.raises(RuntimeError, match="Cannot poll CloudTrail without a boto3 session"):
            source.poll()
