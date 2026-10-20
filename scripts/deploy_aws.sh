#!/usr/bin/env bash
# Deploy FieldLens with the AWS SAM CLI.
#
# This script was NOT run for the repository's evidence: no AWS credentials were
# available and no AWS resource was created. It performs a real deployment only;
# it never fakes one. Requires the AWS CLI, the SAM CLI and a credential source.
set -euo pipefail
cd "$(dirname "$0")/.."

STACK_NAME="${STACK_NAME:-fieldlens}"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
STAGE="${STAGE:-demo}"

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

echo "deploy_aws.sh: performs a REAL deployment and requires AWS credentials."
command -v aws >/dev/null 2>&1 || die "AWS CLI not found in PATH; deployment needs the AWS CLI plus credentials. NOTHING WAS DEPLOYED."
command -v sam >/dev/null 2>&1 || die "AWS SAM CLI not found in PATH; deployment needs the SAM CLI plus AWS credentials. NOTHING WAS DEPLOYED."

echo "== credentials (region ${REGION}) =="
if ! aws sts get-caller-identity --region "$REGION" >/dev/null 2>&1; then
  cat >&2 <<'MSG'
ERROR: no usable AWS credentials. NOTHING WAS BUILT OR DEPLOYED.

This step requires an AWS account with permissions for Lambda, S3, API Gateway,
IAM and CloudFormation. Provide credentials through one of:
  aws configure
  AWS_PROFILE=<profile> scripts/deploy_aws.sh
  AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN

The repository stays deployable without credentials: template.yaml is validated
by `sam validate`, and the handler runs locally against a synthetic event.
MSG
  exit 1
fi
aws sts get-caller-identity --region "$REGION"

echo "== validate =="
sam validate --template-file template.yaml --region "$REGION"

echo "== build =="
sam build --template-file template.yaml

echo "== deploy (CloudFormation change set) =="
sam deploy \
  --template-file .aws-sam/build/template.yaml \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides "Stage=${STAGE}" \
  --resolve-s3 \
  --no-fail-on-empty-changeset

echo "== outputs =="
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs' \
  --output table
