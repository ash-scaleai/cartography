"""
VCR-style cassette recording and playback for provider API responses.

Cassettes are plain JSON files containing recorded API responses. They are
designed to be easy to diff in pull requests and to serve as the basis for
contract tests that detect breaking shape changes in provider APIs.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

logger = logging.getLogger(__name__)


@dataclass
class Cassette:
    """A recorded API response cassette.

    Attributes:
        module_name: The cartography module that produced this data
            (e.g. "aws.ec2.instances").
        api_name: The specific API call recorded
            (e.g. "describe_instances").
        response_data: The raw API response as a dict or list.
        recorded_at: ISO-8601 timestamp of when the cassette was recorded.
        schema_version: Version string for the cassette format itself,
            allowing forward-compatible evolution.
    """

    module_name: str
    api_name: str
    response_data: Union[Dict[str, Any], List[Any]]
    recorded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: str = "1.0"


def save_cassette(cassette: Cassette, path: Union[str, Path]) -> Path:
    """Persist a cassette to a JSON file.

    Args:
        cassette: The Cassette instance to save.
        path: Destination file path.

    Returns:
        The resolved Path that was written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        json.dump(asdict(cassette), fh, indent=2, default=str)
    logger.info("Saved cassette to %s", path)
    return path


def load_cassette(path: Union[str, Path]) -> Cassette:
    """Load a cassette from a JSON file.

    Args:
        path: Path to the cassette JSON file.

    Returns:
        A Cassette instance populated from the file.

    Raises:
        FileNotFoundError: If the cassette file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
        KeyError: If required cassette fields are missing.
    """
    path = Path(path)
    with open(path) as fh:
        data = json.load(fh)
    return Cassette(
        module_name=data["module_name"],
        api_name=data["api_name"],
        response_data=data["response_data"],
        recorded_at=data.get("recorded_at", ""),
        schema_version=data.get("schema_version", "1.0"),
    )


class CassetteRecorder:
    """Records API responses during a real sync run.

    Usage::

        recorder = CassetteRecorder(module_name="aws.ec2.instances")
        recorder.record("describe_instances", api_response)
        recorder.save_all("/path/to/cassettes/")

    The recorder can also wrap a callable so that calls are transparently
    recorded::

        wrapped = recorder.wrap("describe_instances", original_api_func)
        result = wrapped(**kwargs)  # result is recorded automatically
    """

    def __init__(self, module_name: str, schema_version: str = "1.0") -> None:
        self.module_name = module_name
        self.schema_version = schema_version
        self._cassettes: List[Cassette] = []

    @property
    def cassettes(self) -> List[Cassette]:
        """Return all cassettes recorded so far."""
        return list(self._cassettes)

    def record(
        self,
        api_name: str,
        response_data: Union[Dict[str, Any], List[Any]],
        recorded_at: Optional[str] = None,
    ) -> Cassette:
        """Record a single API response.

        Args:
            api_name: Name of the API call (e.g. "describe_instances").
            response_data: The raw API response payload.
            recorded_at: Optional explicit timestamp; defaults to now.

        Returns:
            The newly created Cassette.
        """
        cassette = Cassette(
            module_name=self.module_name,
            api_name=api_name,
            response_data=response_data,
            recorded_at=recorded_at or datetime.now(timezone.utc).isoformat(),
            schema_version=self.schema_version,
        )
        self._cassettes.append(cassette)
        logger.debug(
            "Recorded cassette for %s.%s",
            self.module_name,
            api_name,
        )
        return cassette

    def wrap(self, api_name: str, func: Callable[..., Any]) -> Callable[..., Any]:
        """Return a wrapper that records the result of *func*.

        Args:
            api_name: Name to label the recorded response.
            func: The original API callable.

        Returns:
            A new callable with identical signature whose return value
            is automatically recorded as a cassette.
        """

        def _wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            self.record(api_name, result)
            return result

        return _wrapper

    def save_all(self, directory: Union[str, Path]) -> List[Path]:
        """Save every recorded cassette to *directory*.

        Files are named ``{module_name}__{api_name}.json``.

        Returns:
            List of paths written.
        """
        directory = Path(directory)
        paths: List[Path] = []
        for cassette in self._cassettes:
            filename = f"{cassette.module_name}__{cassette.api_name}.json"
            p = save_cassette(cassette, directory / filename)
            paths.append(p)
        return paths
