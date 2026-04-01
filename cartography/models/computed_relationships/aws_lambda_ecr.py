"""
Schema-declared computed relationships for Lambda to ECR Image analysis.

This replaces the JSON analysis job at:
    cartography/data/jobs/analysis/aws_lambda_ecr.json
"""
from cartography.models.core.computed import AnalysisJob
from cartography.models.core.computed import ComputedRelationship


AWS_LAMBDA_TO_ECR_IMAGE = ComputedRelationship(
    name='Lambda functions with ECR images',
    source_label='AWSLambda',
    target_label='ECRImage',
    relationship_type='HAS',
    cypher_match='(source:AWSLambda), (target:ECRImage)',
    cypher_where="target.digest = 'sha256:' + source.codesha256",
    cleanup_iterative=False,
)

AWS_LAMBDA_ECR_ANALYSIS = AnalysisJob(
    name='Lambda functions with ECR images',
    computed_relationships=[AWS_LAMBDA_TO_ECR_IMAGE],
)
