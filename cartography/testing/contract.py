"""
Contract testing for provider APIs.

Contract tests validate that recorded API cassettes still match the expected
data shape. They do **not** test exact values — only field presence and types.
A breaking change is defined as a Pydantic model validation failure on cassette
data (missing required fields or incompatible types).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Set
from typing import Tuple
from typing import Type
from typing import Union

from pydantic import BaseModel
from pydantic import ValidationError

from cartography.testing.cassette import Cassette
from cartography.testing.cassette import load_cassette

logger = logging.getLogger(__name__)


@dataclass
class ShapeChange:
    """Describes a single shape difference between two cassettes.

    Attributes:
        field: Dot-delimited path to the changed field
            (e.g. "Reservations.0.Instances.0.InstanceId").
        change_type: One of "removed", "type_changed", or "added".
        old_value: Human-readable description of the old state (type name
            or ``None`` for additions).
        new_value: Human-readable description of the new state (type name
            or ``None`` for removals).
    """

    field: str
    change_type: str  # "removed" | "type_changed" | "added"
    old_value: Optional[str]
    new_value: Optional[str]

    def is_breaking(self) -> bool:
        """Return True if this change is considered breaking.

        Removed fields and type changes are breaking; additions are not.
        """
        return self.change_type in ("removed", "type_changed")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _type_name(value: Any) -> str:
    """Return a human-readable type name for *value*."""
    if value is None:
        return "null"
    return type(value).__name__


def _extract_shape(data: Any, prefix: str = "") -> Dict[str, str]:
    """Recursively extract a ``{dotted_path: type_name}`` mapping.

    For lists, only the first element is inspected (representative shape).
    """
    shape: Dict[str, str] = {}
    if isinstance(data, dict):
        for key, val in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            shape[full_key] = _type_name(val)
            shape.update(_extract_shape(val, full_key))
    elif isinstance(data, list) and data:
        # Use first element as representative
        full_key = f"{prefix}[]" if prefix else "[]"
        shape[full_key] = _type_name(data[0])
        shape.update(_extract_shape(data[0], full_key))
    return shape


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class ContractTest:
    """Validates cassettes against Pydantic models and detects shape drift."""

    @staticmethod
    def validate_cassette(cassette: Cassette, model_class: Type[BaseModel]) -> List[str]:
        """Validate a cassette's response_data against a Pydantic model.

        If ``response_data`` is a list, every element is validated individually.

        Args:
            cassette: The cassette to validate.
            model_class: A Pydantic BaseModel that describes the expected shape.

        Returns:
            A list of validation error strings. An empty list means success.
        """
        errors: List[str] = []
        items: List[Any]
        if isinstance(cassette.response_data, list):
            items = cassette.response_data
        else:
            items = [cassette.response_data]

        for idx, item in enumerate(items):
            try:
                model_class.model_validate(item)
            except ValidationError as exc:
                for err in exc.errors():
                    loc = ".".join(str(part) for part in err["loc"])
                    errors.append(
                        f"[{cassette.module_name}:{cassette.api_name}] "
                        f"item {idx}, field '{loc}': {err['msg']}"
                    )
        return errors

    @staticmethod
    def compare_cassettes(old: Cassette, new: Cassette) -> List[ShapeChange]:
        """Compare two cassettes and return shape changes.

        This examines **shape only** (field names and types), not values.

        Args:
            old: The baseline cassette.
            new: The updated cassette.

        Returns:
            A list of ShapeChange instances describing differences.
        """
        old_shape = _extract_shape(old.response_data)
        new_shape = _extract_shape(new.response_data)

        old_keys: Set[str] = set(old_shape.keys())
        new_keys: Set[str] = set(new_shape.keys())

        changes: List[ShapeChange] = []

        # Removed fields (breaking)
        for key in sorted(old_keys - new_keys):
            changes.append(
                ShapeChange(
                    field=key,
                    change_type="removed",
                    old_value=old_shape[key],
                    new_value=None,
                ),
            )

        # Added fields (non-breaking)
        for key in sorted(new_keys - old_keys):
            changes.append(
                ShapeChange(
                    field=key,
                    change_type="added",
                    old_value=None,
                    new_value=new_shape[key],
                ),
            )

        # Type changes (breaking)
        for key in sorted(old_keys & new_keys):
            if old_shape[key] != new_shape[key]:
                changes.append(
                    ShapeChange(
                        field=key,
                        change_type="type_changed",
                        old_value=old_shape[key],
                        new_value=new_shape[key],
                    ),
                )

        return changes

    @staticmethod
    def run_contract_tests(
        cassette_dir: Union[str, Path],
        model_registry: Dict[str, Type[BaseModel]],
    ) -> Dict[str, List[str]]:
        """Run all cassette files in a directory against their models.

        Args:
            cassette_dir: Path to directory containing ``*.json`` cassette files.
            model_registry: Mapping of ``module_name`` to the Pydantic model
                class that should validate the cassette's ``response_data``.

        Returns:
            A dict mapping cassette file names to their validation error lists.
            Files whose ``module_name`` has no registry entry are skipped with
            a logged warning.
        """
        cassette_dir = Path(cassette_dir)
        results: Dict[str, List[str]] = {}

        for cassette_path in sorted(cassette_dir.glob("*.json")):
            cassette = load_cassette(cassette_path)
            model_class = model_registry.get(cassette.module_name)
            if model_class is None:
                logger.warning(
                    "No model registered for module '%s' (cassette: %s) — skipping",
                    cassette.module_name,
                    cassette_path.name,
                )
                continue
            errors = ContractTest.validate_cassette(cassette, model_class)
            results[cassette_path.name] = errors

        return results
