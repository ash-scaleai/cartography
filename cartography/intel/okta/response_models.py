"""
Pydantic response models for Okta API responses.

These models validate the transformed data shapes that cartography's Okta
sync modules produce before loading into Neo4j.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel
from pydantic import ConfigDict


class OktaUserResponse(BaseModel):
    """Transformed Okta user record as produced by transform_okta_user."""

    model_config = ConfigDict(extra="allow")

    id: str
    first_name: str
    last_name: str
    login: str
    email: str
    created: str
    activated: Optional[str] = None
    status_changed: Optional[str] = None
    last_login: Optional[str] = None
    okta_last_updated: Optional[str] = None
    password_changed: Optional[str] = None
    transition_to_status: Optional[str] = None


class OktaGroupResponse(BaseModel):
    """Transformed Okta group record as produced by transform_okta_group."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    description: Optional[str] = None
    sam_account_name: Optional[str] = None
    dn: Optional[str] = None
    windows_domain_qualified_name: Optional[str] = None
    external_id: Optional[str] = None
