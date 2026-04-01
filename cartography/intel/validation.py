"""
Pydantic-based validation utilities for API response data.

This module provides a generic validate_response() function that validates
raw API response data (list[dict] or single dict) against a Pydantic model.
It is designed to be called between get() and transform()/load() in the sync
pipeline, but does NOT modify the existing sync flow -- callers opt in.
"""
import logging
from typing import Any
from typing import Type
from typing import TypeVar
from typing import Union

from pydantic import BaseModel
from pydantic import ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def validate_response(
    data: Union[dict[str, Any], list[dict[str, Any]]],
    model: Type[T],
    *,
    raise_on_error: bool = False,
    context: str = "",
) -> list[T]:
    """
    Validate API response data against a Pydantic model.

    Accepts either a single dict or a list of dicts.  Returns a list of
    validated model instances.

    When *raise_on_error* is False (the default), invalid items are logged
    at WARNING level and silently dropped so that a single malformed record
    does not break the whole sync.  When True, the first ``ValidationError``
    is re-raised immediately -- useful in tests.

    :param data: Raw API response payload (single dict or list of dicts).
    :param model: The Pydantic model class to validate against.
    :param raise_on_error: If True, raise ValidationError on first failure.
    :param context: Optional human-readable label used in log messages
        (e.g. ``"EC2 instances"``).
    :return: List of validated model instances.
    """
    if isinstance(data, dict):
        items = [data]
    else:
        items = data

    label = context or model.__name__

    validated: list[T] = []
    for idx, item in enumerate(items):
        try:
            validated.append(model.model_validate(item))
        except ValidationError as exc:
            if raise_on_error:
                raise
            logger.warning(
                "Validation failed for %s item %d: %s",
                label,
                idx,
                exc.errors(),
            )

    return validated
