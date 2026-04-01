"""
Pydantic response models for AWS Lambda API responses.

These models validate the transformed data shapes that cartography's Lambda
sync module produces before loading into Neo4j.
"""
from __future__ import annotations

from typing import Any
from typing import Optional

from pydantic import BaseModel
from pydantic import ConfigDict


class LambdaFunctionResponse(BaseModel):
    """Transformed Lambda function record as produced by transform_lambda_functions."""

    model_config = ConfigDict(extra="allow")

    FunctionName: str
    FunctionArn: str
    Runtime: Optional[str] = None
    Role: Optional[str] = None
    Handler: Optional[str] = None
    CodeSize: Optional[int] = None
    Description: Optional[str] = None
    Timeout: Optional[int] = None
    MemorySize: Optional[int] = None
    LastModified: Optional[str] = None
    Version: Optional[str] = None
    TracingConfigMode: Optional[str] = None
    Region: str
    AnonymousAccess: Optional[bool] = None
    AnonymousActions: Optional[list[Any]] = None


class LambdaAliasResponse(BaseModel):
    """Transformed Lambda function alias record."""

    model_config = ConfigDict(extra="allow")

    AliasArn: str
    Name: str
    FunctionVersion: Optional[str] = None
    Description: Optional[str] = None
    FunctionArn: str


class LambdaLayerResponse(BaseModel):
    """Transformed Lambda layer record."""

    model_config = ConfigDict(extra="allow")

    Arn: str
    CodeSize: Optional[int] = None
    FunctionArn: str


class LambdaEventSourceMappingResponse(BaseModel):
    """Transformed Lambda event source mapping record."""

    model_config = ConfigDict(extra="allow")

    UUID: str
    EventSourceArn: Optional[str] = None
    FunctionArn: Optional[str] = None
    State: Optional[str] = None
    BatchSize: Optional[int] = None
