"""
Pydantic response models for AWS DynamoDB API responses.

These models validate the transformed data shapes that cartography's DynamoDB
sync module produces before loading into Neo4j.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel
from pydantic import ConfigDict


class DynamoDBTableResponse(BaseModel):
    """Transformed DynamoDB table record as produced by transform_dynamodb_tables."""

    model_config = ConfigDict(extra="allow")

    Arn: str
    TableName: str
    Region: str
    Rows: Optional[int] = None
    Size: Optional[int] = None
    TableStatus: Optional[str] = None
    CreationDateTime: Optional[str] = None
    ProvisionedThroughputReadCapacityUnits: int
    ProvisionedThroughputWriteCapacityUnits: int


class DynamoDBGSIResponse(BaseModel):
    """Transformed DynamoDB Global Secondary Index record."""

    model_config = ConfigDict(extra="allow")

    Arn: str
    TableArn: str
    Region: str
    GSIName: str
    ProvisionedThroughputReadCapacityUnits: int
    ProvisionedThroughputWriteCapacityUnits: int


class DynamoDBBillingResponse(BaseModel):
    """Transformed DynamoDB billing mode summary record."""

    model_config = ConfigDict(extra="allow")

    Id: str
    TableArn: str
    BillingMode: Optional[str] = None
    LastUpdateToPayPerRequestDateTime: Optional[str] = None


class DynamoDBStreamResponse(BaseModel):
    """Transformed DynamoDB stream record."""

    model_config = ConfigDict(extra="allow")

    Arn: str
    TableArn: str
    StreamLabel: Optional[str] = None
    StreamEnabled: Optional[bool] = None
    StreamViewType: Optional[str] = None


class DynamoDBSSEResponse(BaseModel):
    """Transformed DynamoDB SSE description record."""

    model_config = ConfigDict(extra="allow")

    Id: str
    TableArn: str
    SSEStatus: Optional[str] = None
    SSEType: Optional[str] = None
    KMSMasterKeyArn: Optional[str] = None
