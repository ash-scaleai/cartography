"""
Kubernetes CLI option definitions for cartography.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "Kubernetes Options"
MODULE_NAME = "kubernetes"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "k8s_kubeconfig",
        str | None,
        "--k8s-kubeconfig",
        "Path to kubeconfig file for K8s cluster(s).",
        None,
        {},
    ),
    (
        "managed_kubernetes",
        str | None,
        "--managed-kubernetes",
        "Type of managed Kubernetes service (e.g., 'eks').",
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    return {
        "k8s_kubeconfig": args.get("k8s_kubeconfig"),
        "managed_kubernetes": args.get("managed_kubernetes"),
    }
