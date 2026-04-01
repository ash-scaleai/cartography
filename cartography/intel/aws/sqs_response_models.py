"""
Pydantic response models for AWS SQS API responses.

These models validate the transformed data shapes that cartography's SQS
sync module produces before loading into Neo4j.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel
from pydantic import ConfigDict


class SQSQueueResponse(BaseModel):
    """Transformed SQS queue record as produced by transform_sqs_queues."""

    model_config = ConfigDict(extra="allow")

    QueueArn: str
    url: str
    name: str
    CreatedTimestamp: Optional[int] = None
    LastModifiedTimestamp: Optional[int] = None
    VisibilityTimeout: Optional[str] = None
    MaximumMessageSize: Optional[str] = None
    MessageRetentionPeriod: Optional[str] = None
    DelaySeconds: Optional[str] = None
    redrive_policy_dead_letter_target_arn: Optional[str] = None
    redrive_policy_max_receive_count: Optional[int] = None
