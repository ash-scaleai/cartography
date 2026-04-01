"""
Pydantic response models for AWS EKS API responses.

These models validate the transformed data shapes that cartography's EKS
sync module produces before loading into Neo4j.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel
from pydantic import ConfigDict


class EKSClusterResponse(BaseModel):
    """Transformed EKS cluster record as produced by the transform function."""

    model_config = ConfigDict(extra="allow")

    name: str
    arn: str
    version: Optional[str] = None
    platformVersion: Optional[str] = None
    status: Optional[str] = None
    roleArn: Optional[str] = None
    endpoint: Optional[str] = None
    created_at: Optional[str] = None
    ClusterLogging: Optional[bool] = None
    ClusterEndpointPublic: Optional[bool] = None
    certificate_authority_data_present: Optional[bool] = None
    certificate_authority_parse_status: Optional[str] = None
    certificate_authority_sha256_fingerprint: Optional[str] = None
    certificate_authority_subject: Optional[str] = None
    certificate_authority_issuer: Optional[str] = None
