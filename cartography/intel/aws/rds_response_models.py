"""
Pydantic response models for AWS RDS API responses.

These models validate the transformed data shapes that cartography's RDS
sync module produces before loading into Neo4j.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel
from pydantic import ConfigDict


class RDSInstanceResponse(BaseModel):
    """Transformed RDS instance record as produced by transform_rds_instances."""

    model_config = ConfigDict(extra="allow")

    DBInstanceIdentifier: str
    DBInstanceArn: str
    DBInstanceClass: Optional[str] = None
    Engine: Optional[str] = None
    EngineVersion: Optional[str] = None
    DBInstanceStatus: Optional[str] = None
    MasterUsername: Optional[str] = None
    AllocatedStorage: Optional[int] = None
    AvailabilityZone: Optional[str] = None
    MultiAZ: Optional[bool] = None
    PubliclyAccessible: Optional[bool] = None
    StorageEncrypted: Optional[bool] = None
    StorageType: Optional[str] = None
    EndpointAddress: Optional[str] = None
    EndpointPort: Optional[int] = None
    EndpointHostedZoneId: Optional[str] = None
    InstanceCreateTime: Optional[str] = None
    LatestRestorableTime: Optional[str] = None


class RDSClusterResponse(BaseModel):
    """Transformed RDS cluster record as produced by transform_rds_clusters."""

    model_config = ConfigDict(extra="allow")

    DBClusterIdentifier: str
    DBClusterArn: str
    Engine: Optional[str] = None
    EngineVersion: Optional[str] = None
    Status: Optional[str] = None
    MasterUsername: Optional[str] = None
    AllocatedStorage: Optional[int] = None
    MultiAZ: Optional[bool] = None
    StorageEncrypted: Optional[bool] = None
    ClusterCreateTime: Optional[str] = None
    EarliestRestorableTime: Optional[str] = None
    LatestRestorableTime: Optional[str] = None
    EarliestBacktrackTime: Optional[str] = None
    ScalingConfigurationInfoMinCapacity: Optional[int] = None
    ScalingConfigurationInfoMaxCapacity: Optional[int] = None
    ScalingConfigurationInfoAutoPause: Optional[bool] = None


class RDSSnapshotResponse(BaseModel):
    """Transformed RDS snapshot record."""

    model_config = ConfigDict(extra="allow")

    DBSnapshotIdentifier: str
    DBSnapshotArn: str
    DBInstanceIdentifier: Optional[str] = None
    Engine: Optional[str] = None
    SnapshotCreateTime: Optional[str] = None
    InstanceCreateTime: Optional[str] = None
    Status: Optional[str] = None
    SnapshotType: Optional[str] = None
    Encrypted: Optional[bool] = None
