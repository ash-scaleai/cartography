"""
Pydantic response models for AWS Route53 API responses.

These models validate the transformed data shapes that cartography's Route53
sync module produces before loading into Neo4j.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel
from pydantic import ConfigDict


class Route53ZoneResponse(BaseModel):
    """Transformed Route53 hosted zone record as produced by transform_zone."""

    model_config = ConfigDict(extra="allow")

    zoneid: str
    name: str
    privatezone: bool
    comment: Optional[str] = None
    count: Optional[int] = None


class Route53RecordResponse(BaseModel):
    """Transformed Route53 DNS record as produced by transform_record_set."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    type: str
    zoneid: str
    value: Optional[str] = None


class Route53NameServerResponse(BaseModel):
    """Transformed Route53 name server record."""

    model_config = ConfigDict(extra="allow")

    id: str
    zoneid: str
