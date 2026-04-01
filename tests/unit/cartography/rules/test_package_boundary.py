"""
Tests that rules only imports from allowed modules.

Allowed modules:
  - stdlib
  - cartography.rules.*  (intra-package)
  - cartography.client.core.tx  (will become cartography.core in standalone)
  - neo4j / typer / pydantic / typing_extensions  (declared third-party deps)

This test inspects actual source files, not runtime state.
"""

import ast
import pathlib

import pytest

_RULES_DIR = pathlib.Path(__file__).resolve().parents[4] / "cartography" / "rules"

_ALLOWED_PREFIXES = (
    "cartography.rules",
    "cartography.client.core.tx",
    # cartography.util contains helpers (e.g. to_datetime) used by some rule
    # definitions.  These would move to cartography-core in a standalone split.
    "cartography.util",
    # Third-party
    "neo4j",
    "typer",
    "pydantic",
    "typing_extensions",
)

_STDLIB_MODULES = {
    "builtins", "dataclasses", "datetime", "enum", "json", "logging", "os",
    "re", "typing", "urllib",
}


def _collect_imports(filepath: pathlib.Path) -> list[str]:
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
    for p in _RULES_DIR.rglob("*.py"):
        if p.name == "package_info.py":
            continue
        yield p


@pytest.mark.parametrize(
    "filepath",
    list(_get_python_files()),
    ids=lambda p: p.relative_to(_RULES_DIR).as_posix(),
)
def test_rules_imports_are_allowed(filepath):
    """Every import in rules must come from an allowed module."""
    for module_name in _collect_imports(filepath):
        assert _is_allowed(module_name), (
            f"{filepath.name} imports '{module_name}' which is not in the "
            f"allowed set for a standalone rules package."
        )
