import pytest

from cartography.events.models import CloudEvent
from cartography.events.models import EventRoute


class TestCloudEvent:
    def test_create_valid_event(self) -> None:
        event = CloudEvent(
            source="aws.cloudtrail",
            event_type="RunInstances",
            region="us-east-1",
            account_id="123456789012",
            timestamp=1700000000,
        )
        assert event.source == "aws.cloudtrail"
        assert event.event_type == "RunInstances"
        assert event.region == "us-east-1"
        assert event.account_id == "123456789012"
        assert event.timestamp == 1700000000
        assert event.resource_id is None
        assert event.raw_data == {}

    def test_create_event_with_all_fields(self) -> None:
        raw = {"key": "value"}
        event = CloudEvent(
            source="aws.cloudtrail",
            event_type="RunInstances",
            region="us-west-2",
            account_id="123456789012",
            timestamp=1700000000,
            resource_id="i-1234567890abcdef0",
            raw_data=raw,
        )
        assert event.resource_id == "i-1234567890abcdef0"
        assert event.raw_data == {"key": "value"}

    def test_empty_source_raises(self) -> None:
        with pytest.raises(ValueError, match="source must not be empty"):
            CloudEvent(
                source="",
                event_type="RunInstances",
                region="us-east-1",
                account_id="123456789012",
                timestamp=1700000000,
            )

    def test_empty_event_type_raises(self) -> None:
        with pytest.raises(ValueError, match="event_type must not be empty"):
            CloudEvent(
                source="aws.cloudtrail",
                event_type="",
                region="us-east-1",
                account_id="123456789012",
                timestamp=1700000000,
            )

    def test_empty_region_raises(self) -> None:
        with pytest.raises(ValueError, match="region must not be empty"):
            CloudEvent(
                source="aws.cloudtrail",
                event_type="RunInstances",
                region="",
                account_id="123456789012",
                timestamp=1700000000,
            )

    def test_empty_account_id_raises(self) -> None:
        with pytest.raises(ValueError, match="account_id must not be empty"):
            CloudEvent(
                source="aws.cloudtrail",
                event_type="RunInstances",
                region="us-east-1",
                account_id="",
                timestamp=1700000000,
            )

    def test_invalid_timestamp_raises(self) -> None:
        with pytest.raises(ValueError, match="timestamp must be a positive integer"):
            CloudEvent(
                source="aws.cloudtrail",
                event_type="RunInstances",
                region="us-east-1",
                account_id="123456789012",
                timestamp=0,
            )

    def test_negative_timestamp_raises(self) -> None:
        with pytest.raises(ValueError, match="timestamp must be a positive integer"):
            CloudEvent(
                source="aws.cloudtrail",
                event_type="RunInstances",
                region="us-east-1",
                account_id="123456789012",
                timestamp=-1,
            )

    def test_event_is_frozen(self) -> None:
        event = CloudEvent(
            source="aws.cloudtrail",
            event_type="RunInstances",
            region="us-east-1",
            account_id="123456789012",
            timestamp=1700000000,
        )
        with pytest.raises(AttributeError):
            event.source = "changed"  # type: ignore[misc]


class TestEventRoute:
    def test_create_valid_route(self) -> None:
        route = EventRoute(
            event_pattern=r"^RunInstances$",
            target_module="ec2:instance",
        )
        assert route.event_pattern == r"^RunInstances$"
        assert route.target_module == "ec2:instance"
        assert route.use_event_region is True

    def test_create_route_with_region_false(self) -> None:
        route = EventRoute(
            event_pattern=r"^CreateRole$",
            target_module="iam",
            use_event_region=False,
        )
        assert route.use_event_region is False

    def test_empty_pattern_raises(self) -> None:
        with pytest.raises(ValueError, match="event_pattern must not be empty"):
            EventRoute(event_pattern="", target_module="ec2:instance")

    def test_empty_target_raises(self) -> None:
        with pytest.raises(ValueError, match="target_module must not be empty"):
            EventRoute(event_pattern=r"^RunInstances$", target_module="")

    def test_invalid_regex_raises(self) -> None:
        with pytest.raises(Exception):
            EventRoute(event_pattern=r"[invalid", target_module="ec2:instance")
