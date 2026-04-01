"""
Pydantic response models for AWS SNS API responses.

These models validate the transformed data shapes that cartography's SNS
sync module produces before loading into Neo4j.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel
from pydantic import ConfigDict


class SNSTopicResponse(BaseModel):
    """Transformed SNS topic record as produced by transform_sns_topics."""

    model_config = ConfigDict(extra="allow")

    TopicArn: str
    TopicName: str
    DisplayName: Optional[str] = None
    Owner: Optional[str] = None
    SubscriptionsPending: Optional[int] = None
    SubscriptionsConfirmed: Optional[int] = None
    SubscriptionsDeleted: Optional[int] = None
    DeliveryPolicy: Optional[str] = None
    EffectiveDeliveryPolicy: Optional[str] = None
    KmsMasterKeyId: Optional[str] = None


class SNSSubscriptionResponse(BaseModel):
    """SNS topic subscription record."""

    model_config = ConfigDict(extra="allow")

    SubscriptionArn: str
    TopicArn: str
    Protocol: Optional[str] = None
    Endpoint: Optional[str] = None
    Owner: Optional[str] = None
