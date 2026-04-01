"""Tests for cartography.docs.generator - schema-driven documentation."""
from dataclasses import dataclass

from cartography.docs.generator import (
    discover_all_schemas,
    extract_node_info,
    extract_properties,
    extract_rel_properties,
    extract_relationship,
    generate_index_doc,
    generate_module_doc,
    group_schemas_by_provider,
    NodeInfo,
    PropertyInfo,
    RelationshipInfo,
    SchemaDocGenerator,
)
from cartography.models.core.common import PropertyRef
from cartography.models.core.nodes import CartographyNodeProperties
from cartography.models.core.nodes import CartographyNodeSchema
from cartography.models.core.nodes import ExtraNodeLabels
from cartography.models.core.relationships import CartographyRelProperties
from cartography.models.core.relationships import CartographyRelSchema
from cartography.models.core.relationships import LinkDirection
from cartography.models.core.relationships import make_target_node_matcher
from cartography.models.core.relationships import OtherRelationships
from cartography.models.core.relationships import TargetNodeMatcher


# ---------- Test fixtures: minimal model classes ----------

@dataclass(frozen=True)
class _TestNodeProperties(CartographyNodeProperties):
    id: PropertyRef = PropertyRef('arn')
    lastupdated: PropertyRef = PropertyRef('lastupdated', set_in_kwargs=True)
    name: PropertyRef = PropertyRef('Name')
    region: PropertyRef = PropertyRef('Region', set_in_kwargs=True)
    arn: PropertyRef = PropertyRef('Arn', extra_index=True)


@dataclass(frozen=True)
class _TestRelProperties(CartographyRelProperties):
    lastupdated: PropertyRef = PropertyRef('lastupdated', set_in_kwargs=True)


@dataclass(frozen=True)
class _TestSubResourceRel(CartographyRelSchema):
    target_node_label: str = 'AWSAccount'
    target_node_matcher: TargetNodeMatcher = make_target_node_matcher(
        {'id': PropertyRef('AccountId', set_in_kwargs=True)},
    )
    direction: LinkDirection = LinkDirection.INWARD
    rel_label: str = 'RESOURCE'
    properties: _TestRelProperties = _TestRelProperties()


@dataclass(frozen=True)
class _TestOtherRel(CartographyRelSchema):
    target_node_label: str = 'AWSVpc'
    target_node_matcher: TargetNodeMatcher = make_target_node_matcher(
        {'id': PropertyRef('VpcId')},
    )
    direction: LinkDirection = LinkDirection.OUTWARD
    rel_label: str = 'MEMBER_OF_VPC'
    properties: _TestRelProperties = _TestRelProperties()


@dataclass(frozen=True)
class _TestNodeSchema(CartographyNodeSchema):
    label: str = 'TestNode'
    properties: _TestNodeProperties = _TestNodeProperties()
    sub_resource_relationship: _TestSubResourceRel = _TestSubResourceRel()
    other_relationships: OtherRelationships = OtherRelationships([_TestOtherRel()])
    extra_node_labels: ExtraNodeLabels = ExtraNodeLabels(['ExtraLabel', 'AnotherLabel'])


@dataclass(frozen=True)
class _EmptyNodeProperties(CartographyNodeProperties):
    id: PropertyRef = PropertyRef('id')
    lastupdated: PropertyRef = PropertyRef('lastupdated', set_in_kwargs=True)


@dataclass(frozen=True)
class _EmptyNodeSchema(CartographyNodeSchema):
    label: str = 'EmptyNode'
    properties: _EmptyNodeProperties = _EmptyNodeProperties()


# ---------- Tests ----------

class TestPropertyExtraction:
    def test_extract_properties_names_and_count(self):
        props = extract_properties(_TestNodeProperties())
        names = [p.name for p in props]
        assert 'id' in names
        assert 'lastupdated' in names
        assert 'name' in names
        assert 'region' in names
        assert 'arn' in names
        assert len(props) == 5

    def test_extract_properties_sorted(self):
        props = extract_properties(_TestNodeProperties())
        names = [p.name for p in props]
        assert names == sorted(names)

    def test_extract_properties_set_in_kwargs(self):
        props = extract_properties(_TestNodeProperties())
        kwargs_props = {p.name: p for p in props}
        assert kwargs_props['lastupdated'].set_in_kwargs is True
        assert kwargs_props['region'].set_in_kwargs is True
        assert kwargs_props['name'].set_in_kwargs is False

    def test_extract_properties_extra_index(self):
        props = extract_properties(_TestNodeProperties())
        indexed = {p.name: p for p in props}
        assert indexed['arn'].extra_index is True
        assert indexed['name'].extra_index is False

    def test_extract_properties_source_field(self):
        props = extract_properties(_TestNodeProperties())
        by_name = {p.name: p for p in props}
        assert by_name['name'].source_field == 'Name'
        assert by_name['arn'].source_field == 'Arn'
        assert by_name['id'].source_field == 'arn'

    def test_extract_rel_properties(self):
        props = extract_rel_properties(_TestRelProperties())
        assert len(props) == 1
        assert props[0].name == 'lastupdated'
        assert props[0].set_in_kwargs is True


class TestRelationshipExtraction:
    def test_extract_sub_resource_relationship(self):
        rel = extract_relationship(_TestSubResourceRel(), is_sub_resource=True)
        assert rel.rel_label == 'RESOURCE'
        assert rel.target_node_label == 'AWSAccount'
        assert rel.direction == 'INWARD'
        assert rel.is_sub_resource is True

    def test_extract_other_relationship(self):
        rel = extract_relationship(_TestOtherRel(), is_sub_resource=False)
        assert rel.rel_label == 'MEMBER_OF_VPC'
        assert rel.target_node_label == 'AWSVpc'
        assert rel.direction == 'OUTWARD'
        assert rel.is_sub_resource is False

    def test_relationship_has_properties(self):
        rel = extract_relationship(_TestSubResourceRel(), is_sub_resource=True)
        assert len(rel.properties) == 1
        assert rel.properties[0].name == 'lastupdated'


class TestNodeInfoExtraction:
    def test_extract_node_info_label(self):
        info = extract_node_info(_TestNodeSchema())
        assert info.label == 'TestNode'

    def test_extract_node_info_extra_labels(self):
        info = extract_node_info(_TestNodeSchema())
        assert 'AnotherLabel' in info.extra_labels
        assert 'ExtraLabel' in info.extra_labels
        assert info.extra_labels == sorted(info.extra_labels)

    def test_extract_node_info_properties_count(self):
        info = extract_node_info(_TestNodeSchema())
        assert len(info.properties) == 5

    def test_extract_node_info_relationships(self):
        info = extract_node_info(_TestNodeSchema())
        assert len(info.relationships) == 2
        rel_labels = [r.rel_label for r in info.relationships]
        assert 'RESOURCE' in rel_labels
        assert 'MEMBER_OF_VPC' in rel_labels

    def test_extract_node_info_relationships_sorted(self):
        info = extract_node_info(_TestNodeSchema())
        labels = [r.rel_label for r in info.relationships]
        assert labels == sorted(labels)

    def test_extract_node_info_class_name(self):
        info = extract_node_info(_TestNodeSchema())
        assert info.class_name == '_TestNodeSchema'


class TestEmptyModel:
    def test_empty_node_no_extra_labels(self):
        info = extract_node_info(_EmptyNodeSchema())
        assert info.extra_labels == []

    def test_empty_node_no_relationships(self):
        info = extract_node_info(_EmptyNodeSchema())
        assert info.relationships == []

    def test_empty_node_minimal_properties(self):
        info = extract_node_info(_EmptyNodeSchema())
        names = [p.name for p in info.properties]
        assert 'id' in names
        assert 'lastupdated' in names
        assert len(info.properties) == 2

    def test_empty_node_generates_doc(self):
        info = extract_node_info(_EmptyNodeSchema())
        doc = generate_module_doc([info], 'test')
        assert '## EmptyNode' in doc
        assert '| id |' in doc
        assert '### Relationships' not in doc


class TestDocGeneration:
    def test_generate_module_doc_contains_header(self):
        info = extract_node_info(_TestNodeSchema())
        doc = generate_module_doc([info], 'aws')
        assert '# AWS Schema' in doc

    def test_generate_module_doc_contains_toc(self):
        info = extract_node_info(_TestNodeSchema())
        doc = generate_module_doc([info], 'aws')
        assert '## Table of Contents' in doc
        assert '- [TestNode]' in doc

    def test_generate_module_doc_contains_node_section(self):
        info = extract_node_info(_TestNodeSchema())
        doc = generate_module_doc([info], 'aws')
        assert '## TestNode' in doc

    def test_generate_module_doc_contains_extra_labels(self):
        info = extract_node_info(_TestNodeSchema())
        doc = generate_module_doc([info], 'aws')
        assert '**Extra Labels:**' in doc
        assert 'AnotherLabel' in doc
        assert 'ExtraLabel' in doc

    def test_generate_module_doc_contains_properties_table(self):
        info = extract_node_info(_TestNodeSchema())
        doc = generate_module_doc([info], 'aws')
        assert '| name | Name | No | No |' in doc
        assert '| arn | Arn | No | Yes |' in doc
        assert '| region | Region | Yes | No |' in doc

    def test_generate_module_doc_contains_relationships_table(self):
        info = extract_node_info(_TestNodeSchema())
        doc = generate_module_doc([info], 'aws')
        assert '| INWARD | RESOURCE | AWSAccount | Yes |' in doc
        assert '| OUTWARD | MEMBER_OF_VPC | AWSVpc | No |' in doc

    def test_generate_index_doc(self):
        doc = generate_index_doc(['aws', 'github', 'gcp'])
        assert '# Cartography Schema Documentation' in doc
        assert '- [AWS](modules/aws/schema.md)' in doc
        assert '- [GitHub](modules/github/schema.md)' in doc
        assert '- [GCP](modules/gcp/schema.md)' in doc

    def test_generate_index_doc_sorted(self):
        doc = generate_index_doc(['github', 'aws', 'gcp'])
        aws_pos = doc.index('AWS')
        gcp_pos = doc.index('GCP')
        github_pos = doc.index('GitHub')
        assert aws_pos < gcp_pos < github_pos


class TestDeterministicOutput:
    def test_same_output_twice(self):
        info = extract_node_info(_TestNodeSchema())
        doc1 = generate_module_doc([info], 'aws')
        doc2 = generate_module_doc([info], 'aws')
        assert doc1 == doc2

    def test_same_index_twice(self):
        keys = ['github', 'aws', 'gcp', 'azure']
        doc1 = generate_index_doc(keys)
        doc2 = generate_index_doc(keys)
        assert doc1 == doc2

    def test_multiple_nodes_deterministic(self):
        info1 = extract_node_info(_TestNodeSchema())
        info2 = extract_node_info(_EmptyNodeSchema())
        doc_a = generate_module_doc([info1, info2], 'test')
        doc_b = generate_module_doc([info1, info2], 'test')
        assert doc_a == doc_b


class TestDiscovery:
    def test_discover_finds_schemas(self):
        """Discover should find at least some schemas from the models package."""
        schemas = discover_all_schemas('cartography.models')
        assert len(schemas) > 0

    def test_discover_returns_node_schemas(self):
        schemas = discover_all_schemas('cartography.models')
        for s in schemas:
            assert isinstance(s, CartographyNodeSchema)

    def test_discover_finds_known_models(self):
        """We know EC2Instance and AWSUser models exist."""
        schemas = discover_all_schemas('cartography.models')
        labels = [s.label for s in schemas]
        assert 'EC2Instance' in labels
        assert 'AWSUser' in labels
        assert 'GitHubUser' in labels

    def test_discover_sorted_by_label(self):
        schemas = discover_all_schemas('cartography.models')
        labels = [(s.label, type(s).__name__) for s in schemas]
        assert labels == sorted(labels)


class TestGroupByProvider:
    def test_group_schemas_by_provider(self):
        schemas = discover_all_schemas('cartography.models')
        grouped = group_schemas_by_provider(schemas)
        assert 'aws' in grouped
        assert 'github' in grouped
        assert len(grouped['aws']) > 0

    def test_provider_key_extraction(self):
        """Schemas from aws.ec2.instances should be in 'aws' provider."""
        schemas = discover_all_schemas('cartography.models')
        grouped = group_schemas_by_provider(schemas)
        aws_labels = [n.label for n in grouped['aws']]
        assert 'EC2Instance' in aws_labels


class TestSchemaDocGeneratorClass:
    def test_generate_all_docs_returns_dict(self):
        gen = SchemaDocGenerator(output_dir='/tmp/test-schema-docs')
        docs = gen.generate_all_docs()
        assert isinstance(docs, dict)
        assert 'aws/schema.md' in docs
        assert 'github/schema.md' in docs
        assert 'index.md' in docs

    def test_generate_all_docs_content(self):
        gen = SchemaDocGenerator(output_dir='/tmp/test-schema-docs')
        docs = gen.generate_all_docs()
        assert '# AWS Schema' in docs['aws/schema.md']
        assert '# GitHub Schema' in docs['github/schema.md']

    def test_write_all_docs(self, tmp_path):
        gen = SchemaDocGenerator(output_dir=str(tmp_path))
        written = gen.write_all_docs()
        assert len(written) > 0
        # Check files exist
        for path in written:
            assert (tmp_path / path.replace(str(tmp_path) + '/', '')).exists()

    def test_write_all_docs_deterministic(self, tmp_path):
        """Running the generator twice produces identical output."""
        dir1 = tmp_path / 'run1'
        dir2 = tmp_path / 'run2'

        gen1 = SchemaDocGenerator(output_dir=str(dir1))
        gen1.write_all_docs()

        gen2 = SchemaDocGenerator(output_dir=str(dir2))
        gen2.write_all_docs()

        # Compare all files
        for path in sorted(dir1.rglob('*.md')):
            rel = path.relative_to(dir1)
            path2 = dir2 / rel
            assert path2.exists(), f"Missing file in second run: {rel}"
            assert path.read_text() == path2.read_text(), f"Content differs for {rel}"
