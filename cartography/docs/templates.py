"""
Markdown templates for schema-driven documentation generation.

These templates are used by the SchemaDocGenerator to produce consistent,
readable Markdown documentation from cartography model classes.
"""

MODULE_HEADER = """\
# {provider_name} Schema

> Auto-generated from cartography model classes. Do not edit manually.

"""

TABLE_OF_CONTENTS_HEADER = """\
## Table of Contents

"""

TABLE_OF_CONTENTS_ENTRY = """\
- [{label}](#{anchor})
"""

NODE_SECTION_HEADER = """\
## {label}

"""

NODE_EXTRA_LABELS = """\
**Extra Labels:** {labels}

"""

NODE_PROPERTIES_TABLE_HEADER = """\
### Properties

| Property | Source Field | Is Kwargs | Extra Index |
|----------|-------------|-----------|-------------|
"""

NODE_PROPERTIES_TABLE_ROW = """\
| {name} | {source_field} | {is_kwargs} | {extra_index} |
"""

RELATIONSHIP_SECTION_HEADER = """\
### Relationships

"""

RELATIONSHIP_TABLE_HEADER = """\
| Direction | Relationship | Target Node | Sub Resource |
|-----------|-------------|-------------|--------------|
"""

RELATIONSHIP_TABLE_ROW = """\
| {direction} | {rel_label} | {target_label} | {is_sub_resource} |
"""

INDEX_HEADER = """\
# Cartography Schema Documentation

> Auto-generated from cartography model classes. Do not edit manually.

## Modules

"""

INDEX_ENTRY = """\
- [{provider_name}](modules/{provider_key}/schema.md)
"""
