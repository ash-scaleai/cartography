"""
Data models for event-driven incremental sync.

Defines the CloudEvent and EventRoute dataclasses used throughout the
event-driven sync system.
"""
import re
from dataclasses import dataclass
from dataclasses import field
from typing import Optional


@dataclass(frozen=True)
class CloudEvent:
    """
    Represents a cloud infrastructure event that may trigger an incremental sync.

    Attributes:
        source: The origin of the event, e.g. "aws.cloudtrail".
        event_type: The type of event, e.g. "RunInstances", "CreateBucket".
        region: The cloud region where the event occurred, e.g. "us-east-1".
        account_id: The cloud account identifier, e.g. an AWS account ID.
        timestamp: Unix timestamp (seconds) of when the event occurred.
        resource_id: Optional identifier for the specific resource affected.
        raw_data: The original event payload as a dictionary.
    """
    source: str
    event_type: str
    region: str
    account_id: str
    timestamp: int
    resource_id: Optional[str] = None
    raw_data: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError("CloudEvent.source must not be empty")
        if not self.event_type:
            raise ValueError("CloudEvent.event_type must not be empty")
        if not self.region:
            raise ValueError("CloudEvent.region must not be empty")
        if not self.account_id:
            raise ValueError("CloudEvent.account_id must not be empty")
        if not isinstance(self.timestamp, int) or self.timestamp <= 0:
            raise ValueError("CloudEvent.timestamp must be a positive integer")


@dataclass(frozen=True)
class EventRoute:
    """
    Maps an event pattern to a cartography sync target module.

    The event_pattern is a regex that is matched against the event_type
    field of a CloudEvent. If it matches, the target_module is the
    cartography AWS resource function key (from RESOURCE_FUNCTIONS) that
    should be re-synced.

    Attributes:
        event_pattern: A regex pattern matched against CloudEvent.event_type.
        target_module: The cartography module key to sync, e.g. "ec2:instance", "s3".
        use_event_region: If True, scope the re-sync to the event's region only.
    """
    event_pattern: str
    target_module: str
    use_event_region: bool = True

    def __post_init__(self) -> None:
        if not self.event_pattern:
            raise ValueError("EventRoute.event_pattern must not be empty")
        if not self.target_module:
            raise ValueError("EventRoute.target_module must not be empty")
        # Validate regex compiles
        re.compile(self.event_pattern)
