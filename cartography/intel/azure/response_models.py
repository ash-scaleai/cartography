"""
Pydantic response models for Azure API responses.

These models validate the transformed data shapes that cartography's Azure
sync modules produce before loading into Neo4j.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel
from pydantic import ConfigDict


class AzureVirtualMachineResponse(BaseModel):
    """Azure VM record as returned by the compute module's get_vm_list."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: Optional[str] = None
    location: Optional[str] = None
    resource_group: Optional[str] = None
    type: Optional[str] = None


class AzureSubscriptionResponse(BaseModel):
    """Azure subscription record as produced by the subscription module."""

    model_config = ConfigDict(extra="allow")

    id: str
    subscriptionId: str
    displayName: Optional[str] = None
    state: Optional[str] = None
