"""
Schema-driven documentation generator for cartography models.

Discovers all CartographyNodeSchema subclasses in cartography/models/,
extracts their labels, properties, and relationships, and generates
Markdown documentation per provider module.

Usage:
    python -m cartography.docs.generator [--output-dir docs/root/modules]
"""
import argparse
import dataclasses
import importlib
import inspect
import logging
import os
import pkgutil
import sys
from dataclasses import fields as dataclass_fields
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from cartography.docs import templates
from cartography.models.core.common import PropertyRef
from cartography.models.core.nodes import CartographyNodeProperties
from cartography.models.core.nodes import CartographyNodeSchema
from cartography.models.core.nodes import ExtraNodeLabels
from cartography.models.core.relationships import CartographyRelProperties
from cartography.models.core.relationships import CartographyRelSchema
from cartography.models.core.relationships import LinkDirection
from cartography.models.core.relationships import OtherRelationships

logger = logging.getLogger(__name__)


class PropertyInfo:
    """Extracted information about a single node or relationship property."""

    def __init__(self, name: str, source_field: str, set_in_kwargs: bool, extra_index: bool):
        self.name = name
        self.source_field = source_field
        self.set_in_kwargs = set_in_kwargs
        self.extra_index = extra_index

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PropertyInfo):
            return NotImplemented
        return (
            self.name == other.name
            and self.source_field == other.source_field
            and self.set_in_kwargs == other.set_in_kwargs
            and self.extra_index == other.extra_index
        )

    def __repr__(self) -> str:
        return (
            f"PropertyInfo(name={self.name!r}, source_field={self.source_field!r}, "
            f"set_in_kwargs={self.set_in_kwargs!r}, extra_index={self.extra_index!r})"
        )


class RelationshipInfo:
    """Extracted information about a single relationship."""

    def __init__(
        self,
        rel_label: str,
        target_node_label: str,
        direction: str,
        is_sub_resource: bool,
        properties: List[PropertyInfo],
    ):
        self.rel_label = rel_label
        self.target_node_label = target_node_label
        self.direction = direction
        self.is_sub_resource = is_sub_resource
        self.properties = properties

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RelationshipInfo):
            return NotImplemented
        return (
            self.rel_label == other.rel_label
            and self.target_node_label == other.target_node_label
            and self.direction == other.direction
            and self.is_sub_resource == other.is_sub_resource
            and self.properties == other.properties
        )

    def __repr__(self) -> str:
        return (
            f"RelationshipInfo(rel_label={self.rel_label!r}, "
            f"target_node_label={self.target_node_label!r}, "
            f"direction={self.direction!r}, "
            f"is_sub_resource={self.is_sub_resource!r})"
        )


class NodeInfo:
    """Extracted information about a single node schema."""

    def __init__(
        self,
        label: str,
        extra_labels: List[str],
        properties: List[PropertyInfo],
        relationships: List[RelationshipInfo],
        class_name: str,
        module_name: str,
    ):
        self.label = label
        self.extra_labels = extra_labels
        self.properties = properties
        self.relationships = relationships
        self.class_name = class_name
        self.module_name = module_name

    def __repr__(self) -> str:
        return f"NodeInfo(label={self.label!r}, class_name={self.class_name!r})"


def extract_properties(props_instance: CartographyNodeProperties) -> List[PropertyInfo]:
    """
    Extract property information from a CartographyNodeProperties instance.

    Uses dataclass field introspection to find all PropertyRef fields.

    Args:
        props_instance: An instance of a CartographyNodeProperties subclass.

    Returns:
        A sorted list of PropertyInfo objects.
    """
    result = []
    for f in dataclass_fields(props_instance):
        value = getattr(props_instance, f.name)
        if isinstance(value, PropertyRef):
            result.append(PropertyInfo(
                name=f.name,
                source_field=value.name,
                set_in_kwargs=value.set_in_kwargs,
                extra_index=value.extra_index,
            ))
    result.sort(key=lambda p: p.name)
    return result


def extract_rel_properties(props_instance: CartographyRelProperties) -> List[PropertyInfo]:
    """
    Extract property information from a CartographyRelProperties instance.

    Args:
        props_instance: An instance of a CartographyRelProperties subclass.

    Returns:
        A sorted list of PropertyInfo objects.
    """
    result = []
    for f in dataclass_fields(props_instance):
        value = getattr(props_instance, f.name)
        if isinstance(value, PropertyRef):
            result.append(PropertyInfo(
                name=f.name,
                source_field=value.name,
                set_in_kwargs=value.set_in_kwargs,
                extra_index=value.extra_index,
            ))
    result.sort(key=lambda p: p.name)
    return result


def extract_relationship(rel: CartographyRelSchema, is_sub_resource: bool) -> RelationshipInfo:
    """
    Extract relationship information from a CartographyRelSchema instance.

    Args:
        rel: An instance of a CartographyRelSchema subclass.
        is_sub_resource: Whether this relationship is the sub resource relationship.

    Returns:
        A RelationshipInfo object.
    """
    direction_str = "INWARD" if rel.direction == LinkDirection.INWARD else "OUTWARD"
    rel_props = extract_rel_properties(rel.properties)
    return RelationshipInfo(
        rel_label=rel.rel_label,
        target_node_label=rel.target_node_label,
        direction=direction_str,
        is_sub_resource=is_sub_resource,
        properties=rel_props,
    )


def extract_node_info(schema_instance: CartographyNodeSchema) -> NodeInfo:
    """
    Extract all information from a CartographyNodeSchema instance.

    Args:
        schema_instance: An instance of a CartographyNodeSchema subclass.

    Returns:
        A NodeInfo object containing all extracted information.
    """
    # Extract label
    label = schema_instance.label

    # Extract extra labels
    extra_labels: List[str] = []
    if schema_instance.extra_node_labels is not None:
        for lbl in schema_instance.extra_node_labels.labels:
            if isinstance(lbl, str):
                extra_labels.append(lbl)
            else:
                # ConditionalNodeLabel
                extra_labels.append(f"{lbl.label} (conditional)")
    extra_labels.sort()

    # Extract properties
    properties = extract_properties(schema_instance.properties)

    # Extract relationships
    relationships: List[RelationshipInfo] = []
    if schema_instance.sub_resource_relationship is not None:
        relationships.append(
            extract_relationship(schema_instance.sub_resource_relationship, is_sub_resource=True),
        )
    if schema_instance.other_relationships is not None:
        for rel in schema_instance.other_relationships.rels:
            relationships.append(
                extract_relationship(rel, is_sub_resource=False),
            )
    relationships.sort(key=lambda r: (r.rel_label, r.target_node_label))

    return NodeInfo(
        label=label,
        extra_labels=extra_labels,
        properties=properties,
        relationships=relationships,
        class_name=type(schema_instance).__name__,
        module_name=type(schema_instance).__module__,
    )


def _import_submodules_recursive(package_name: str) -> None:
    """
    Recursively import all submodules of a package so that all subclasses are registered.

    Args:
        package_name: Dotted package name, e.g. 'cartography.models'.
    """
    try:
        package = importlib.import_module(package_name)
    except ImportError:
        logger.warning("Could not import package %s", package_name)
        return

    package_path = getattr(package, '__path__', None)
    if package_path is None:
        return

    for _importer, modname, ispkg in pkgutil.walk_packages(
        package_path, prefix=package_name + '.',
    ):
        try:
            importlib.import_module(modname)
        except Exception:
            logger.warning("Could not import module %s", modname, exc_info=True)


def discover_all_schemas(models_package: str = 'cartography.models') -> List[CartographyNodeSchema]:
    """
    Discover all CartographyNodeSchema subclasses by importing the models package.

    Returns:
        A list of instantiated CartographyNodeSchema subclasses, sorted by label.
    """
    _import_submodules_recursive(models_package)

    schemas: List[CartographyNodeSchema] = []
    seen_classes: set = set()

    def _find_subclasses(cls: type) -> None:
        for subclass in cls.__subclasses__():
            if subclass in seen_classes:
                continue
            seen_classes.add(subclass)
            if not inspect.isabstract(subclass):
                try:
                    instance = subclass()
                    schemas.append(instance)
                except Exception:
                    logger.warning(
                        "Could not instantiate schema class %s",
                        subclass.__name__,
                        exc_info=True,
                    )
            _find_subclasses(subclass)

    _find_subclasses(CartographyNodeSchema)
    schemas.sort(key=lambda s: (s.label, type(s).__name__))
    return schemas


def _provider_key_from_module(module_name: str) -> str:
    """
    Extract the provider key from a module name.

    e.g. 'cartography.models.aws.ec2.instances' -> 'aws'
         'cartography.models.github.users' -> 'github'
    """
    parts = module_name.split('.')
    try:
        models_idx = parts.index('models')
        if models_idx + 1 < len(parts):
            return parts[models_idx + 1]
    except ValueError:
        pass
    return 'unknown'


def _provider_display_name(key: str) -> str:
    """Convert a provider key to a display name."""
    name_map = {
        'aws': 'AWS',
        'gcp': 'GCP',
        'oci': 'OCI',
        'cve': 'CVE',
        'gsuite': 'GSuite',
        'github': 'GitHub',
        'gitlab': 'GitLab',
        'azure': 'Azure',
        'duo': 'Duo',
        'okta': 'Okta',
        'aibom': 'AIBOM',
        'ssm': 'SSM',
    }
    return name_map.get(key, key.replace('_', ' ').title())


def group_schemas_by_provider(
    schemas: List[CartographyNodeSchema],
) -> Dict[str, List[NodeInfo]]:
    """
    Group schema instances by provider, extracting NodeInfo for each.

    Args:
        schemas: List of CartographyNodeSchema instances.

    Returns:
        A dict mapping provider key -> sorted list of NodeInfo.
    """
    grouped: Dict[str, List[NodeInfo]] = {}
    for schema in schemas:
        info = extract_node_info(schema)
        provider = _provider_key_from_module(info.module_name)
        grouped.setdefault(provider, []).append(info)

    # Sort nodes within each provider for deterministic output
    for key in grouped:
        grouped[key].sort(key=lambda n: (n.label, n.class_name))

    return grouped


def generate_module_doc(nodes: List[NodeInfo], provider_key: str) -> str:
    """
    Generate Markdown documentation for a single provider module.

    Args:
        nodes: List of NodeInfo objects for this provider.
        provider_key: The provider key (e.g. 'aws', 'github').

    Returns:
        A Markdown string.
    """
    provider_name = _provider_display_name(provider_key)
    doc = templates.MODULE_HEADER.format(provider_name=provider_name)

    # Table of contents
    doc += templates.TABLE_OF_CONTENTS_HEADER
    for node in nodes:
        anchor = node.label.lower()
        # For duplicate labels, include class name
        doc += templates.TABLE_OF_CONTENTS_ENTRY.format(label=node.label, anchor=anchor)
    doc += "\n"

    # Node sections
    for node in nodes:
        doc += templates.NODE_SECTION_HEADER.format(label=node.label)

        if node.extra_labels:
            doc += templates.NODE_EXTRA_LABELS.format(labels=', '.join(node.extra_labels))

        # Properties table
        doc += templates.NODE_PROPERTIES_TABLE_HEADER
        for prop in node.properties:
            doc += templates.NODE_PROPERTIES_TABLE_ROW.format(
                name=prop.name,
                source_field=prop.source_field,
                is_kwargs="Yes" if prop.set_in_kwargs else "No",
                extra_index="Yes" if prop.extra_index else "No",
            )
        doc += "\n"

        # Relationships
        if node.relationships:
            doc += templates.RELATIONSHIP_SECTION_HEADER
            doc += templates.RELATIONSHIP_TABLE_HEADER
            for rel in node.relationships:
                doc += templates.RELATIONSHIP_TABLE_ROW.format(
                    direction=rel.direction,
                    rel_label=rel.rel_label,
                    target_label=rel.target_node_label,
                    is_sub_resource="Yes" if rel.is_sub_resource else "No",
                )
            doc += "\n"

    return doc


def generate_index_doc(provider_keys: List[str]) -> str:
    """
    Generate the index page listing all provider modules.

    Args:
        provider_keys: Sorted list of provider keys.

    Returns:
        A Markdown string for the index page.
    """
    doc = templates.INDEX_HEADER
    for key in sorted(provider_keys):
        doc += templates.INDEX_ENTRY.format(
            provider_name=_provider_display_name(key),
            provider_key=key,
        )
    return doc


class SchemaDocGenerator:
    """
    Main class for generating schema documentation from cartography models.

    Discovers all model classes, extracts schema information, and writes
    Markdown documentation to the specified output directory.
    """

    def __init__(self, output_dir: str = 'docs/root/modules'):
        """
        Initialize the generator.

        Args:
            output_dir: Path to the output directory for generated docs.
        """
        self.output_dir = output_dir
        self._schemas: Optional[List[CartographyNodeSchema]] = None
        self._grouped: Optional[Dict[str, List[NodeInfo]]] = None

    def discover(self, models_package: str = 'cartography.models') -> List[CartographyNodeSchema]:
        """Discover all schema classes. Results are cached."""
        if self._schemas is None:
            self._schemas = discover_all_schemas(models_package)
        return self._schemas

    def get_grouped_schemas(self, models_package: str = 'cartography.models') -> Dict[str, List[NodeInfo]]:
        """Group discovered schemas by provider. Results are cached."""
        if self._grouped is None:
            schemas = self.discover(models_package)
            self._grouped = group_schemas_by_provider(schemas)
        return self._grouped

    def generate_all_docs(self, models_package: str = 'cartography.models') -> Dict[str, str]:
        """
        Generate documentation for all discovered models.

        Returns:
            A dict mapping file paths (relative to output_dir) to Markdown content.
        """
        grouped = self.get_grouped_schemas(models_package)
        docs: Dict[str, str] = {}

        for provider_key, nodes in sorted(grouped.items()):
            filepath = os.path.join(provider_key, 'schema.md')
            docs[filepath] = generate_module_doc(nodes, provider_key)

        # Index page
        docs['index.md'] = generate_index_doc(list(grouped.keys()))

        return docs

    def write_all_docs(self, models_package: str = 'cartography.models') -> List[str]:
        """
        Generate and write all documentation to disk.

        Returns:
            A list of file paths that were written.
        """
        docs = self.generate_all_docs(models_package)
        written: List[str] = []

        for rel_path, content in sorted(docs.items()):
            full_path = os.path.join(self.output_dir, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w') as f:
                f.write(content)
            written.append(full_path)
            logger.info("Wrote %s", full_path)

        return written


def main() -> None:
    """CLI entry point for generating schema documentation."""
    parser = argparse.ArgumentParser(
        description='Generate schema documentation from cartography model classes.',
    )
    parser.add_argument(
        '--output-dir',
        default='docs/root/modules',
        help='Output directory for generated docs (default: docs/root/modules)',
    )
    parser.add_argument(
        '--models-package',
        default='cartography.models',
        help='Python package to scan for models (default: cartography.models)',
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging',
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(levelname)s: %(message)s',
    )

    generator = SchemaDocGenerator(output_dir=args.output_dir)
    written = generator.write_all_docs(models_package=args.models_package)
    print(f"Generated {len(written)} documentation files.")
    for path in written:
        print(f"  {path}")


if __name__ == '__main__':
    main()
