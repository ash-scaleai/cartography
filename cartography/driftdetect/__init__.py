"""
cartography-driftdetect: Detect drift in your Cartography-managed Neo4j graph.

Public API
----------
* ``CLI`` -- command-line interface class
* ``run_get_states`` -- snapshot current graph state
* ``run_drift_detection`` -- compare two snapshots
* ``run_add_shortcut`` -- create a named alias for a snapshot file
* ``UpdateConfig`` / ``GetDriftConfig`` / ``AddShortcutConfig`` -- config objects
* ``State`` -- in-memory representation of a single drift-detection state
* ``FileSystem`` -- file-based storage backend
"""

from cartography.driftdetect.add_shortcut import add_shortcut
from cartography.driftdetect.add_shortcut import run_add_shortcut
from cartography.driftdetect.cli import CLI
from cartography.driftdetect.config import AddShortcutConfig
from cartography.driftdetect.config import GetDriftConfig
from cartography.driftdetect.config import UpdateConfig
from cartography.driftdetect.detect_deviations import perform_drift_detection
from cartography.driftdetect.detect_deviations import run_drift_detection
from cartography.driftdetect.get_states import run_get_states
from cartography.driftdetect.model import State
from cartography.driftdetect.shortcut import Shortcut
from cartography.driftdetect.storage import FileSystem

__all__ = [
    # CLI
    "CLI",
    # High-level runners
    "run_get_states",
    "run_drift_detection",
    "run_add_shortcut",
    "add_shortcut",
    "perform_drift_detection",
    # Config
    "UpdateConfig",
    "GetDriftConfig",
    "AddShortcutConfig",
    # Models
    "State",
    "Shortcut",
    # Storage
    "FileSystem",
]
