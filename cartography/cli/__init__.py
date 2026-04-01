"""
Cartography CLI package.

This package provides the command-line interface for cartography. It is split
into a core module (cartography.cli.core) and per-provider CLI modules located
alongside each provider's code (e.g., cartography.intel.aws.cli).

Dynamic plugin discovery for provider CLI options is provided by the registry
module (cartography.cli.registry).

For backward compatibility, this __init__.py re-exports the key symbols that
were previously available from the monolithic cartography.cli module:

    - CLI: The main CLI class
    - main: The default entrypoint function
    - STATUS_SUCCESS, STATUS_FAILURE, STATUS_KEYBOARD_INTERRUPT: Exit codes
"""
from cartography.cli.core import CLI
from cartography.cli.core import main
from cartography.cli.core import STATUS_FAILURE
from cartography.cli.core import STATUS_KEYBOARD_INTERRUPT
from cartography.cli.core import STATUS_SUCCESS

__all__ = [
    "CLI",
    "main",
    "STATUS_SUCCESS",
    "STATUS_FAILURE",
    "STATUS_KEYBOARD_INTERRUPT",
]
