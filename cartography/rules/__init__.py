"""
cartography-rules: Security rules engine for Cartography.

Public API
----------
* ``run_rules`` -- execute one or more rules against a Neo4j graph
* ``get_all_frameworks`` -- list all compliance frameworks referenced by rules
* ``RULES`` -- registry of all available Rule definitions
* ``Rule``, ``Fact``, ``Finding``, ``Framework`` -- spec model classes
* ``RuleResult``, ``FactResult``, ``CounterResult`` -- result data classes
"""

from cartography.rules.data.rules import RULES
from cartography.rules.runners import get_all_frameworks
from cartography.rules.runners import run_rules
from cartography.rules.spec.model import Fact
from cartography.rules.spec.model import Finding
from cartography.rules.spec.model import Framework
from cartography.rules.spec.model import Maturity
from cartography.rules.spec.model import Module
from cartography.rules.spec.model import Rule
from cartography.rules.spec.result import CounterResult
from cartography.rules.spec.result import FactResult
from cartography.rules.spec.result import RuleResult

__all__ = [
    # Registry
    "RULES",
    # High-level runners
    "run_rules",
    "get_all_frameworks",
    # Spec models
    "Rule",
    "Fact",
    "Finding",
    "Framework",
    "Module",
    "Maturity",
    # Result types
    "RuleResult",
    "FactResult",
    "CounterResult",
]
