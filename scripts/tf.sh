#!/usr/bin/env bash
# Run Terraform in one root for the environment selected with `mise -E <env>`.
#   mise -E dev run tf infra plan
set -euo pipefail

: "${DEPLOY_ENV:?Select an environment, e.g. mise -E dev run tf infra plan}"
: "${TF_VAR_aws_account_id:?Set TF_VAR_aws_account_id in mise.$DEPLOY_ENV.local.toml}"
root="${1:?Usage: tf <bootstrap|infra|platform> <terraform command> [args...]}"
shift

# Stop before Terraform runs if the profile points at another account than this environment expects.
account="$(aws sts get-caller-identity --query Account --output text)"
if [ "$account" != "$TF_VAR_aws_account_id" ]; then
  echo "AWS_PROFILE=$AWS_PROFILE is account $account, but $DEPLOY_ENV expects $TF_VAR_aws_account_id" >&2
  exit 1
fi

# One state bucket per environment account; the account ID keeps the name globally unique.
export TF_VAR_state_bucket_name="contoso-$DEPLOY_ENV-tfstate-$TF_VAR_aws_account_id"
# The platform deploys the image `mise run image` pushed for the committed app code, unless overridden.
export TF_VAR_image_tag="${TF_VAR_image_tag:-$(scripts/image-tag.sh)}"
# Separate provider and backend cache per environment, e.g. infra/.terraform/dev.
export TF_DATA_DIR=".terraform/$DEPLOY_ENV"

if [ "${1:-}" = init ]; then
  shift
  if [ "$root" = bootstrap ]; then
    set -- init -backend-config="path=terraform.$DEPLOY_ENV.tfstate" "$@"
  else
    set -- init -backend-config="bucket=$TF_VAR_state_bucket_name" \
      -backend-config="key=$root.tfstate" -backend-config="region=$AWS_REGION" "$@"
  fi
fi
exec terraform -chdir="$root" "$@"
