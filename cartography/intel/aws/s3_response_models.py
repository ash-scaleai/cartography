"""
Pydantic response models for AWS S3 API data.

Covers the shapes returned by list_buckets and related S3 APIs
that Cartography ingests.
"""
from __future__ import annotations

import datetime
from typing import Any
from typing import Optional

from pydantic import BaseModel
from pydantic import ConfigDict


class S3BucketOwner(BaseModel):
    """The owner of an S3 bucket listing."""

    model_config = ConfigDict(extra="allow")

    DisplayName: Optional[str] = None
    ID: Optional[str] = None


class S3Bucket(BaseModel):
    """A single S3 bucket as returned by list_buckets (with Region enriched by get_bucket_location)."""

    model_config = ConfigDict(extra="allow")

    Name: str
    CreationDate: Optional[datetime.datetime] = None
    # Region is enriched after the list_buckets call via get_bucket_location.
    # It is None for us-east-1 buckets or when the location lookup fails.
    Region: Optional[str] = None


class S3ListBucketsResponse(BaseModel):
    """The full list_buckets response (enriched with Region on each bucket)."""

    model_config = ConfigDict(extra="allow")

    Buckets: list[S3Bucket] = []
    Owner: Optional[S3BucketOwner] = None


class S3GrantGrantee(BaseModel):
    """The grantee in an S3 ACL grant."""

    model_config = ConfigDict(extra="allow")

    Type: str
    DisplayName: Optional[str] = None
    ID: Optional[str] = None
    URI: Optional[str] = None


class S3Grant(BaseModel):
    """A single grant entry within an S3 ACL."""

    model_config = ConfigDict(extra="allow")

    Grantee: S3GrantGrantee
    Permission: str


class S3AclResponse(BaseModel):
    """The get_bucket_acl response."""

    model_config = ConfigDict(extra="allow")

    Owner: Optional[S3BucketOwner] = None
    Grants: list[S3Grant] = []


class S3EncryptionRule(BaseModel):
    """A single server-side encryption rule for a bucket."""

    model_config = ConfigDict(extra="allow")

    ApplyServerSideEncryptionByDefault: Optional[dict[str, Any]] = None
    BucketKeyEnabled: Optional[bool] = None


class S3EncryptionResponse(BaseModel):
    """The get_bucket_encryption response (transformed by cartography)."""

    model_config = ConfigDict(extra="allow")

    bucket: Optional[str] = None
    default_encryption: Optional[bool] = None
    encryption_algorithm: Optional[str] = None
    encryption_key_id: Optional[str] = None
    bucket_key_enabled: Optional[bool] = None
