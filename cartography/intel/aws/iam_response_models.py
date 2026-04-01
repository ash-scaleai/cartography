"""
Pydantic response models for AWS IAM API data.

Covers the shapes returned by list_users, list_roles, list_groups, and
related IAM API calls that Cartography ingests.
"""
from __future__ import annotations

import datetime
from typing import Any
from typing import Optional

from pydantic import BaseModel
from pydantic import ConfigDict


# ---------------------------------------------------------------------------
# IAM Users
# ---------------------------------------------------------------------------

class IAMUser(BaseModel):
    """A single IAM user as returned by list_users."""

    model_config = ConfigDict(extra="allow")

    UserName: str
    UserId: str
    Arn: str
    Path: Optional[str] = None
    CreateDate: Optional[datetime.datetime] = None
    PasswordLastUsed: Optional[datetime.datetime] = None
    Tags: list[dict[str, Any]] = []


class IAMUserListResponse(BaseModel):
    """Wrapper for the paginated list_users response."""

    model_config = ConfigDict(extra="allow")

    Users: list[IAMUser] = []


# ---------------------------------------------------------------------------
# IAM Groups
# ---------------------------------------------------------------------------

class IAMGroup(BaseModel):
    """A single IAM group as returned by list_groups."""

    model_config = ConfigDict(extra="allow")

    GroupName: str
    GroupId: str
    Arn: str
    Path: Optional[str] = None
    CreateDate: Optional[datetime.datetime] = None


class IAMGroupListResponse(BaseModel):
    """Wrapper for the paginated list_groups response."""

    model_config = ConfigDict(extra="allow")

    Groups: list[IAMGroup] = []


# ---------------------------------------------------------------------------
# IAM Roles
# ---------------------------------------------------------------------------

class IAMPolicyStatement(BaseModel):
    """A single statement within an assume-role policy document."""

    model_config = ConfigDict(extra="allow")

    Effect: Optional[str] = None
    Action: Optional[Any] = None  # str or list[str]
    Principal: Optional[Any] = None  # str, dict, or list
    Condition: Optional[dict[str, Any]] = None
    Resource: Optional[Any] = None  # str or list[str]


class IAMAssumeRolePolicyDocument(BaseModel):
    """The trust policy document attached to an IAM role."""

    model_config = ConfigDict(extra="allow")

    Version: Optional[str] = None
    Statement: list[IAMPolicyStatement] = []


class IAMRole(BaseModel):
    """A single IAM role as returned by list_roles."""

    model_config = ConfigDict(extra="allow")

    RoleName: str
    RoleId: str
    Arn: str
    Path: Optional[str] = None
    CreateDate: Optional[datetime.datetime] = None
    AssumeRolePolicyDocument: Optional[IAMAssumeRolePolicyDocument] = None
    Description: Optional[str] = None
    MaxSessionDuration: Optional[int] = None
    Tags: list[dict[str, Any]] = []


class IAMRoleListResponse(BaseModel):
    """Wrapper for the paginated list_roles response."""

    model_config = ConfigDict(extra="allow")

    Roles: list[IAMRole] = []
