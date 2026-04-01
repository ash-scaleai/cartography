"""
Okta CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "Okta Options"
MODULE_NAME = "okta"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "okta_org_id",
        str | None,
        "--okta-org-id",
        "Okta organizational ID to sync. Required for Okta module.",
        None,
        {},
    ),
    (
        "okta_api_key_env_var",
        str | None,
        "--okta-api-key-env-var",
        "Environment variable name containing Okta API key.",
        None,
        {},
    ),
    (
        "okta_base_domain",
        str,
        "--okta-base-domain",
        (
            "Base domain for Okta API requests. Defaults to 'okta.com'. "
            "Set this if your organization uses a custom Okta domain."
        ),
        "okta.com",
        {},
    ),
    (
        "okta_saml_role_regex",
        str,
        "--okta-saml-role-regex",
        "Regex to map Okta groups to AWS roles. Must contain {{role}} and {{accountid}} tags.",
        r"^aws\#\S+\#(?{{role}}[\w\-]+)\#(?{{accountid}}\d+)$",
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    config_kwargs: dict[str, Any] = {}

    okta_api_key = None
    if args.get("okta_org_id") and args.get("okta_api_key_env_var"):
        logger.debug(
            "Reading API key for Okta from environment variable %s",
            args["okta_api_key_env_var"],
        )
        okta_api_key = os.environ.get(args["okta_api_key_env_var"])

    config_kwargs["okta_org_id"] = args.get("okta_org_id")
    config_kwargs["okta_api_key"] = okta_api_key
    config_kwargs["okta_base_domain"] = args.get("okta_base_domain", "okta.com")
    config_kwargs["okta_saml_role_regex"] = args.get(
        "okta_saml_role_regex",
        r"^aws\#\S+\#(?{{role}}[\w\-]+)\#(?{{accountid}}\d+)$",
    )

    return config_kwargs
