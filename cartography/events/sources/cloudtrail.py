"""
CloudTrail event source adapter.

Provides utilities to parse raw CloudTrail events into CloudEvent objects
and a source class that can poll CloudTrail for recent events.
"""
import logging
from typing import Any
from typing import Optional

from cartography.events.models import CloudEvent

logger = logging.getLogger(__name__)


def parse_cloudtrail_event(raw: dict[str, Any]) -> Optional[CloudEvent]:
    """
    Convert a raw CloudTrail event record into a CloudEvent.

    Args:
        raw: A single CloudTrail event record dict. Expected to contain
            at least 'eventName', 'awsRegion', 'recipientAccountId',
            and 'eventTime'.

    Returns:
        A CloudEvent if parsing succeeds, or None if the event is missing
        required fields.
    """
    event_name = raw.get("eventName")
    region = raw.get("awsRegion")
    account_id = raw.get("recipientAccountId") or raw.get("userIdentity", {}).get("accountId")
    event_time = raw.get("eventTime")

    if not event_name or not region or not account_id:
        logger.warning(
            "Skipping CloudTrail event with missing fields: eventName=%s, "
            "awsRegion=%s, accountId=%s",
            event_name,
            region,
            account_id,
        )
        return None

    # Parse eventTime (ISO 8601) to Unix timestamp
    timestamp = _parse_event_time(event_time)
    if timestamp is None:
        logger.warning(
            "Skipping CloudTrail event with unparseable eventTime: %s",
            event_time,
        )
        return None

    # Extract resource ID from requestParameters or responseElements if available
    resource_id = _extract_resource_id(raw)

    return CloudEvent(
        source="aws.cloudtrail",
        event_type=event_name,
        region=region,
        account_id=account_id,
        timestamp=timestamp,
        resource_id=resource_id,
        raw_data=raw,
    )


def _parse_event_time(event_time: Optional[str]) -> Optional[int]:
    """
    Parse a CloudTrail eventTime string (ISO 8601) to a Unix timestamp (int).
    """
    if not event_time:
        return None
    import datetime
    try:
        dt = datetime.datetime.fromisoformat(event_time.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except (ValueError, AttributeError):
        return None


def _extract_resource_id(raw: dict[str, Any]) -> Optional[str]:
    """
    Best-effort extraction of a resource identifier from CloudTrail event data.

    Looks in responseElements and requestParameters for common ID fields.
    """
    # Check responseElements first (for create events)
    response = raw.get("responseElements") or {}
    for key in ("instancesSet", "instanceId", "bucketName", "functionName",
                "roleId", "roleName", "groupId", "keyId", "tableId",
                "clusterName", "queueUrl", "topicArn", "dbInstanceIdentifier"):
        if key in response:
            val = response[key]
            if isinstance(val, dict) and "items" in val:
                # e.g., RunInstances responseElements.instancesSet.items
                items = val["items"]
                if items and isinstance(items, list):
                    first = items[0]
                    if isinstance(first, dict) and "instanceId" in first:
                        return first["instanceId"]
            elif isinstance(val, str):
                return val

    # Check requestParameters (for modify/delete events)
    params = raw.get("requestParameters") or {}
    for key in ("instanceId", "bucketName", "functionName", "roleName",
                "groupId", "keyId", "tableName", "clusterName",
                "queueUrl", "topicArn", "dbInstanceIdentifier"):
        if key in params:
            val = params[key]
            if isinstance(val, str):
                return val

    return None


class CloudTrailEventSource:
    """
    Polls CloudTrail for recent events or accepts pre-fetched events.

    This class is a thin adapter; it does not implement actual queue consumption.
    It can be used to:
    - Accept a list of pre-fetched CloudTrail event records
    - Poll CloudTrail via a boto3 client for recent LookupEvents

    Args:
        boto3_session: An optional boto3 session for CloudTrail API calls.
        region: The region to poll CloudTrail in. Defaults to the session's region.
    """

    def __init__(
        self,
        boto3_session: Any = None,
        region: Optional[str] = None,
    ) -> None:
        self._boto3_session = boto3_session
        self._region = region

    def parse_events(self, raw_events: list[dict[str, Any]]) -> list[CloudEvent]:
        """
        Parse a list of raw CloudTrail event records into CloudEvents.

        Args:
            raw_events: List of CloudTrail event record dicts.

        Returns:
            List of successfully parsed CloudEvent objects.
        """
        events: list[CloudEvent] = []
        for raw in raw_events:
            event = parse_cloudtrail_event(raw)
            if event is not None:
                events.append(event)
        return events

    def poll(
        self,
        lookback_minutes: int = 15,
        max_results: int = 50,
    ) -> list[CloudEvent]:
        """
        Poll CloudTrail LookupEvents for recent write events.

        This is a convenience method for simple use cases. For production
        use, prefer consuming events from an SQS queue or S3 bucket
        notifications.

        Args:
            lookback_minutes: How many minutes back to look for events.
            max_results: Maximum number of events to fetch.

        Returns:
            List of CloudEvent objects parsed from the CloudTrail response.

        Raises:
            RuntimeError: If no boto3_session was provided.
        """
        if not self._boto3_session:
            raise RuntimeError(
                "Cannot poll CloudTrail without a boto3 session. "
                "Provide a boto3_session to CloudTrailEventSource.",
            )

        import datetime

        client_kwargs: dict[str, Any] = {"service_name": "cloudtrail"}
        if self._region:
            client_kwargs["region_name"] = self._region
        client = self._boto3_session.client(**client_kwargs)

        start_time = datetime.datetime.now(
            tz=datetime.timezone.utc,
        ) - datetime.timedelta(minutes=lookback_minutes)

        response = client.lookup_events(
            StartTime=start_time,
            MaxResults=max_results,
            LookupAttributes=[
                {"AttributeKey": "ReadOnly", "AttributeValue": "false"},
            ],
        )

        raw_events = []
        import json
        for event_record in response.get("Events", []):
            cloud_trail_event = event_record.get("CloudTrailEvent")
            if cloud_trail_event:
                try:
                    raw_events.append(json.loads(cloud_trail_event))
                except (json.JSONDecodeError, TypeError):
                    logger.warning(
                        "Failed to parse CloudTrail event JSON: %s",
                        cloud_trail_event[:200] if cloud_trail_event else None,
                    )

        return self.parse_events(raw_events)
