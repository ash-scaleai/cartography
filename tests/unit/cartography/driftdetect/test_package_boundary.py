"""
Tests that driftdetect only imports from allowed modules.

Allowed modules:
  - stdlib
  - cartography.driftdetect.*  (intra-package)
  - cartography.client.core.tx  (will become cartography.core in standalone)
  - neo4j / marshmallow  (declared third-party deps)

This test inspects actual source files, not runtime state, so it works even
if some optional dependencies are missing.
"""

import ast
import pathlib

import pytest

# Root of the driftdetect package
_DRIFTDETECT_DIR = pathlib.Path(__file__).resolve().parents[4] / "cartography" / "driftdetect"

# Allowed top-level import prefixes for driftdetect
_ALLOWED_PREFIXES = (
    "cartography.driftdetect",
    "cartography.client.core.tx",
    # Third-party
    "neo4j",
    "marshmallow",
)

# Standard-library top-level module names that driftdetect actually uses
_STDLIB_MODULES = {
    "argparse", "builtins", "getpass", "json", "logging", "os", "pathlib",
    "sys", "time", "typing",
}


def _collect_imports(filepath: pathlib.Path) -> list[str]:
    """Return all top-level dotted import names from a Python source file."""
    source = filepath.read_text()
    tree = ast.parse(source, filename=str(filepath))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def _is_allowed(module_name: str) -> bool:
    top = module_name.split(".")[0]
    if top in _STDLIB_MODULES:
        return True
    return any(module_name.startswith(prefix) for prefix in _ALLOWED_PREFIXES)


def _get_python_files():
    """Yield all .py files in the driftdetect package (excluding package_info)."""
    for p in _DRIFTDETECT_DIR.rglob("*.py"):
        if p.name == "package_info.py":
            continue
        yield p


@pytest.mark.parametrize(
    "filepath",
    list(_get_python_files()),
    ids=lambda p: p.relative_to(_DRIFTDETECT_DIR).as_posix(),
)
def test_driftdetect_imports_are_allowed(filepath):
    """Every import in driftdetect must come from an allowed module."""
    for module_name in _collect_imports(filepath):
        assert _is_allowed(module_name), (
            f"{filepath.name} imports '{module_name}' which is not in the "
            f"allowed set for a standalone driftdetect package."
        )
