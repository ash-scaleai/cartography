"""
Pydantic response models for GitHub GraphQL API data.

Covers the repository objects returned by the ``GITHUB_ORG_REPOS_PAGINATED_GRAPHQL``
query that Cartography ingests.
"""
from __future__ import annotations

from typing import Any
from typing import Optional

from pydantic import BaseModel
from pydantic import ConfigDict


class GitHubLanguageNode(BaseModel):
    """A single programming language node."""

    model_config = ConfigDict(extra="allow")

    name: str


class GitHubLanguages(BaseModel):
    """Languages summary for a repository."""

    model_config = ConfigDict(extra="allow")

    totalCount: int = 0
    nodes: list[GitHubLanguageNode] = []


class GitHubDefaultBranchRef(BaseModel):
    """Default branch reference for a repository."""

    model_config = ConfigDict(extra="allow")

    name: str
    id: str


class GitHubOwner(BaseModel):
    """Owner of a repository (Organization or User)."""

    model_config = ConfigDict(extra="allow")

    url: str
    login: str
    __typename: Optional[str] = None

    # __typename is a GraphQL field; pydantic treats dunder attrs specially,
    # so we also accept it through extra="allow".


class GitHubPrimaryLanguage(BaseModel):
    """Primary language of a repository."""

    model_config = ConfigDict(extra="allow")

    name: str


class GitHubCollaboratorCount(BaseModel):
    """Collaborator count object."""

    model_config = ConfigDict(extra="allow")

    totalCount: int = 0


class GitHubBranchProtectionRule(BaseModel):
    """A single branch protection rule."""

    model_config = ConfigDict(extra="allow")

    id: str
    pattern: Optional[str] = None
    allowsDeletions: Optional[bool] = None
    allowsForcePushes: Optional[bool] = None
    dismissesStaleReviews: Optional[bool] = None
    isAdminEnforced: Optional[bool] = None
    requiresApprovingReviews: Optional[bool] = None
    requiredApprovingReviewCount: Optional[int] = None
    requiresCodeOwnerReviews: Optional[bool] = None
    requiresCommitSignatures: Optional[bool] = None
    requiresLinearHistory: Optional[bool] = None
    requiresStatusChecks: Optional[bool] = None
    requiresStrictStatusChecks: Optional[bool] = None
    restrictsPushes: Optional[bool] = None
    restrictsReviewDismissals: Optional[bool] = None


class GitHubBranchProtectionRules(BaseModel):
    """Container for branch protection rules."""

    model_config = ConfigDict(extra="allow")

    nodes: list[GitHubBranchProtectionRule] = []


class GitHubBlobContent(BaseModel):
    """Content of a Git blob object (e.g. requirements.txt)."""

    model_config = ConfigDict(extra="allow")

    text: Optional[str] = None


class GitHubRepo(BaseModel):
    """
    A single GitHub repository as returned by the org repos GraphQL query.

    Only the fields that Cartography reads in its transform step are
    required; everything else is optional with ``extra='allow'``.
    """

    model_config = ConfigDict(extra="allow")

    name: str
    nameWithOwner: str
    url: str
    sshUrl: Optional[str] = None
    createdAt: Optional[str] = None
    description: Optional[str] = None
    updatedAt: Optional[str] = None
    homepageUrl: Optional[str] = None
    primaryLanguage: Optional[GitHubPrimaryLanguage] = None
    languages: Optional[GitHubLanguages] = None
    defaultBranchRef: Optional[GitHubDefaultBranchRef] = None
    isPrivate: Optional[bool] = None
    isArchived: Optional[bool] = None
    isDisabled: Optional[bool] = None
    isLocked: Optional[bool] = None
    owner: Optional[GitHubOwner] = None
    directCollaborators: Optional[GitHubCollaboratorCount] = None
    outsideCollaborators: Optional[GitHubCollaboratorCount] = None
    branchProtectionRules: Optional[GitHubBranchProtectionRules] = None
    requirements: Optional[GitHubBlobContent] = None
    setupCfg: Optional[GitHubBlobContent] = None
