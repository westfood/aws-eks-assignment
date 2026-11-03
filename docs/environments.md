# Environments and account targeting

The repository supports `dev`, `test` and `prod` as **three separate AWS accounts**. The live interview presentation uses **dev only**. Creating the configuration files does not create AWS accounts or deploy resources into any environment.

| Target | Intended use | Resource-name example |
| --- | --- | --- |
| `dev` | Interview demonstration and development | `contoso-dev` |
| `test` | Integration and release validation | `contoso-test` |
| `prod` | Production deployment target after operational review | `contoso-prod` |

Account separation provides an AWS authorization boundary between environments. AWS recommends separating production from development and test workloads. This repository does not provision an AWS Organization, Control Tower or account vending. [AWS account separation guidance](https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/aws-account-management-and-separation.html)

## Isolation model

Each target has its own AWS profile and expected account ID, state bucket in that account, Terraform state for `infra` and `platform`, local bootstrap state, Terraform initialization data, plans, outputs and kubeconfig. The application and Terraform source remain shared. Environment-qualified names and tags make the target visible in AWS.

The environment helper checks the selected profile's account before cloud operations. Terraform also restricts its AWS providers to the expected account, and the S3 backend restricts the account used to access state. Platform deployment checks the EKS destination and workload role identities. These checks are independent of the shell's previous `AWS_PROFILE` or current Kubernetes context.

Terraform CLI workspaces are not used to switch accounts. Distinct backend configuration and credentials make the boundaries explicit; a workspace name alone does not provide account isolation. [Terraform workspace guidance](https://developer.hashicorp.com/terraform/cli/workspaces), [S3 backend account restrictions](https://developer.hashicorp.com/terraform/language/backend/s3)

## Configure a target

Copy the selected example to its private input file:

```bash
cp environments/dev.example.json environments/dev.json
# Later, when those separate accounts are ready:
cp environments/test.example.json environments/test.json
cp environments/prod.example.json environments/prod.json
```

Only dev is needed for the presentation. Fill each private file when that account is available; do not reuse dev's account ID to make test/prod configuration appear complete. The `environment` field must match the selected file/target. Replace account, profile, bucket and IAM principal placeholders with confirmed values. Real environment JSON files are ignored by Git.

The file has this structure; use the checked-in example for the complete set of infrastructure options:

```json
{
  "environment": "dev",
  "aws_account_id": "REPLACE_WITH_DEV_ACCOUNT_ID",
  "aws_profile": "contoso-dev",
  "aws_region": "eu-central-1",
  "state_bucket_name": "REPLACE_WITH_A_GLOBALLY_UNIQUE_DEV_BUCKET",
  "infra": {
    "name": "contoso",
    "admin_cidrs": ["203.0.113.10/32"],
    "admin_principal_arn": "arn:aws:iam::123456789012:role/replace-with-dev-deployment-role"
  }
}
```

The account ID must be a real 12-digit value before cloud commands run, and the principal must belong to that account. The example CIDR is documentation-only; replace it with a trusted client address. Supply an IAM role/user ARN rather than an STS session ARN. Configure/login the selected AWS profile separately; the target helper does not create credentials or accounts.

| Setting | Dev example | Test/prod examples |
| --- | --- | --- |
| Resource base name | `contoso` → `contoso-dev` | `contoso` → `contoso-test` / `contoso-prod` |
| NAT | Single gateway for demo cost | One gateway per AZ |
| RDS | Single-AZ | Multi-AZ |
| EKS API | Private path plus CIDR-restricted public API | Same explicit management path; private-only is optional when connected access exists |
| Application | Synthetic interview demo | Shared sample; requires production review before real users/data |

These are configuration choices, not evidence that test/prod have been deployed or approved for production use.

## Run commands against a target

The common prefix is:

```bash
mise run target -- --env dev show
mise run target -- --env dev check
```

`show` inspects the configured target without cloud operations. `check` verifies the AWS identity. Replace `dev` with `test` or `prod` only when deliberately operating that account.

| Command after `--env dev` | Purpose |
| --- | --- |
| `terraform bootstrap init`, `plan`, `apply`, `output` | Create the selected account's state bucket |
| `terraform infra init`, `plan`, `apply`, `output` | Manage selected AWS infrastructure |
| `platform-inputs --image repository@sha256:...` | Generate platform inputs from this target's infra outputs |
| `terraform platform init`, `plan`, `apply`, `output` | Manage selected Helm/Kubernetes resources |
| `aws <arguments>` | Run an AWS CLI operation under the selected account/profile/Region |
| `kubeconfig` | Write the target's dedicated EKS kubeconfig |
| `kubectl <arguments>` | Use that kubeconfig/context |
| `demo` | Read-only presentation checks; accepts dev only |

The helper rejects AWS profile/Region and Kubernetes kubeconfig/context overrides that could bypass the selected target. It clears inherited static AWS credentials, `TF_VAR_*` and `TF_CLI_ARGS*` for child commands and supplies the selected inputs explicitly. Existing root-level `terraform.tfvars`/auto-loaded input files are rejected so they cannot silently override this target.

For presentation checks, the convenience task is also fixed to dev:

```bash
mise run demo
```

## Private artifacts

Each target uses `.local/<environment>/` for generated inputs, backend configuration, Terraform initialization data and saved plans. Managed output files are `bootstrap-outputs.json`, `infra-outputs.json` and `platform-outputs.json` within that directory. The `terraform ... output` helper command writes these files; do not redirect its output over the same managed file.

The dedicated kubeconfigs are `.local/dev/kubeconfig`, `.local/test/kubeconfig` and `.local/prod/kubeconfig`. Existing lab contexts in the normal kubeconfig are preserved. Terraform backend keys and the local bootstrap state are separate for each target, and account restrictions apply to both providers and remote state access. The helper checks the expected S3 bucket owner before remote-backend operations.

Plan/apply commands use target-specific saved-plan manifests. Select the same account/environment, stage and destroy mode for apply; changing inputs requires a fresh plan. For example:

```bash
mise run target -- --env dev terraform infra plan
mise run target -- --env dev terraform infra apply
```

An infrastructure change in test or prod uses its own account, configuration, plan and state rather than dev's artifact files. `--destroy` selects a destroy plan/apply; platform teardown also supports `--ingress-only` to keep the controller available while deleting the ALB. See the root README for the ordered cleanup sequence.

## Promote a change

Use the same reviewed source revision and immutable image version across environments. Build and exercise the change in dev, validate it in test, then create and review a separate prod plan using the prod account and state. Copying a plan or state file between targets is not a promotion mechanism. A plan belongs to its environment and state.

The test/prod configuration examples demonstrate environment-specific choices. Their presence is not a claim that the sample application is production-ready. Before real production use, define recovery and availability objectives, add application authentication, configure verified HTTPS and owned DNS, establish operational alerts, test restores and review deployment permissions. The demonstration application accepts synthetic messages without end-user authentication.

## Existing single-environment checkouts

Do not repoint an existing backend or relabel an existing deployment merely by changing an environment variable. If the earlier single-environment commands were already used, retain their state and backend files and inventory the existing resources first. State relocation and resource renaming need a deliberate migration plan. The current account-free preparation has not deployed an earlier AWS environment.
