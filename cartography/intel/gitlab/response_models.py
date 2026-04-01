"""
Pydantic response models for GitLab API responses.

These models validate the transformed data shapes that cartography's GitLab
sync modules produce before loading into Neo4j.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel
from pydantic import ConfigDict


class GitLabProjectResponse(BaseModel):
    """Transformed GitLab project record as produced by transform_projects."""

    model_config = ConfigDict(extra="allow")

    web_url: str
    name: str
    path: Optional[str] = None
    path_with_namespace: Optional[str] = None
    description: Optional[str] = None
    visibility: Optional[str] = None
    default_branch: Optional[str] = None
    archived: Optional[bool] = None
    created_at: Optional[str] = None
    last_activity_at: Optional[str] = None
    org_url: str
    group_url: Optional[str] = None
    languages: Optional[str] = None


class GitLabGroupResponse(BaseModel):
    """Transformed GitLab group record as produced by transform_groups."""

    model_config = ConfigDict(extra="allow")

    web_url: str
    name: str
    path: Optional[str] = None
    full_path: Optional[str] = None
    description: Optional[str] = None
    visibility: Optional[str] = None
    parent_id: Optional[int] = None
    created_at: Optional[str] = None
    org_url: str
    parent_group_url: Optional[str] = None
