"""
Pydantic response models for GCP Compute Engine API data.

Covers the shapes returned by ``compute.instances().list()`` and related
Compute Engine APIs that Cartography ingests.
"""
from __future__ import annotations

from typing import Any
from typing import Optional

from pydantic import BaseModel
from pydantic import ConfigDict


class GCPAccessConfig(BaseModel):
    """An access configuration on a network interface (external IP)."""

    model_config = ConfigDict(extra="allow")

    name: Optional[str] = None
    natIP: Optional[str] = None
    type: Optional[str] = None
    networkTier: Optional[str] = None
    kind: Optional[str] = None


class GCPNetworkInterface(BaseModel):
    """A network interface on a GCP Compute instance."""

    model_config = ConfigDict(extra="allow")

    name: Optional[str] = None
    network: str
    subnetwork: str
    networkIP: Optional[str] = None
    fingerprint: Optional[str] = None
    accessConfigs: list[GCPAccessConfig] = []
    kind: Optional[str] = None


class GCPAttachedDisk(BaseModel):
    """A disk attached to a GCP Compute instance."""

    model_config = ConfigDict(extra="allow")

    deviceName: Optional[str] = None
    index: Optional[int] = None
    boot: Optional[bool] = None
    autoDelete: Optional[bool] = None
    mode: Optional[str] = None
    source: Optional[str] = None
    type: Optional[str] = None
    interface: Optional[str] = None
    kind: Optional[str] = None
    licenses: list[str] = []
    guestOsFeatures: list[dict[str, Any]] = []


class GCPServiceAccount(BaseModel):
    """A service account attached to a GCP Compute instance."""

    model_config = ConfigDict(extra="allow")

    email: str
    scopes: list[str] = []


class GCPScheduling(BaseModel):
    """Scheduling configuration for a GCP instance."""

    model_config = ConfigDict(extra="allow")

    automaticRestart: Optional[bool] = None
    onHostMaintenance: Optional[str] = None
    preemptible: Optional[bool] = None


class GCPTags(BaseModel):
    """Network tags attached to an instance."""

    model_config = ConfigDict(extra="allow")

    fingerprint: Optional[str] = None
    items: list[str] = []


class GCPInstance(BaseModel):
    """
    A single GCP Compute Engine instance as returned by
    ``compute.instances().list()``.

    Only the fields that Cartography reads in its transform/load step are
    required; everything else is optional with ``extra='allow'``.
    """

    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    selfLink: Optional[str] = None
    zone: Optional[str] = None
    machineType: Optional[str] = None
    status: Optional[str] = None
    creationTimestamp: Optional[str] = None
    description: Optional[str] = None
    canIpForward: Optional[bool] = None
    cpuPlatform: Optional[str] = None
    deletionProtection: Optional[bool] = None
    startRestricted: Optional[bool] = None
    labelFingerprint: Optional[str] = None
    kind: Optional[str] = None
    networkInterfaces: list[GCPNetworkInterface] = []
    disks: list[GCPAttachedDisk] = []
    serviceAccounts: list[GCPServiceAccount] = []
    scheduling: Optional[GCPScheduling] = None
    tags: Optional[GCPTags] = None
    metadata: Optional[dict[str, Any]] = None


class GCPInstanceListResponse(BaseModel):
    """
    The response from ``compute.instances().list()`` for a single zone.
    """

    model_config = ConfigDict(extra="allow")

    id: str
    items: list[GCPInstance] = []
    kind: Optional[str] = None
    selfLink: Optional[str] = None
