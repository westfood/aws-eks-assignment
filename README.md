# Contoso AWS platform demonstration

A small Terraform deployment for an AWS DevOps interview: a web frontend/API on private EKS workers, backed by RDS PostgreSQL in separate isolated subnets. An internet-facing ALB exposes the application. IAM, TLS, security groups and NetworkPolicy protect distinct parts of the request path.

[![Validation](https://github.com/westfood/aws-eks-assignment/actions/workflows/ci.yml/badge.svg)](https://github.com/westfood/aws-eks-assignment/actions/workflows/ci.yml)

**Deployment status:** prepared without an AWS account. The container image and Compose database roundtrip passed in GitHub Actions. An AWS plan/apply, ECR push, ingress, RDS IAM/TLS checks and teardown must still be performed and recorded. CI does not establish live AWS behavior.

Verification on **3 November 2026**: [all five CI jobs passed](https://github.com/westfood/aws-eks-assignment/actions/runs/41646044307) at commit `1c57894`. They validated all three Terraform roots, ran 11 mocked Terraform checks, 23 application tests against PostgreSQL 17 and 6 helper tests, built the actual image, exercised Compose write/read, and checked UID `10001` and a read-only root filesystem. An isolated native PostgreSQL 18.6 instance and a real browser also exercised local desktop/mobile behavior. RDS IAM/TLS and AWS networking remain unverified.

![Architecture](docs/architecture.png)

- [Architecture and network boundaries](docs/architecture.md), [decisions](docs/decisions.md), [editable draw.io diagram](docs/architecture.drawio)
- [Interview walkthrough](docs/interview-walkthrough.md), [cost and cleanup](docs/cost-and-cleanup.md), [primary sources](docs/sources.md)
- Presentation: see `presentation/` for the English stakeholder deck and speaker notes.
- Application: see `app/` for the frontend, database code, tests and image.

The default uses two worker nodes, one NAT Gateway and a Single-AZ database. Two database subnets do not imply a Multi-AZ DB. WAF is enabled by default. This is a demonstration, with synthetic messages and no end-user authentication. The enterprise landing-zone recommendation belongs in the presentation; this repository does not provision Control Tower or an organization-wide landing zone.

## 1. Prepare tools and an AWS identity

Use Terraform `>=1.14,<2`, AWS CLI `>=2.32`, `kubectl`, Python 3.12+, Docker with Buildx and Git. Run commands from the repository root in a Bash/Zsh terminal. Set a restrictive file-creation mask for local plans, outputs and kubeconfig:

```bash
git clone https://github.com/westfood/aws-eks-assignment.git
cd aws-eks-assignment
umask 077
mkdir -p .local
terraform version
aws --version
kubectl version --client
python3 --version
docker buildx version
```

If there is no account yet, create one at [AWS signup](https://portal.aws.amazon.com/billing/signup), secure its root login with MFA and configure billing alerts. Use the root identity only for account setup. Choose a plan that permits the required services and review the estimate in [cost and cleanup](docs/cost-and-cleanup.md); EKS is not an automatically free lab. [Root-user guidance](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_root-user.html)

For a fresh standalone account, create a console IAM user with MFA or use an existing federated role. Grant `SignInLocalDevelopmentAccess` for browser-based CLI login. For this disposable lab, the deployment identity also needs administrative permissions to create IAM roles, EKS access entries and networking; ordinary `PowerUserAccess` is insufficient for IAM creation. Production should use a reviewed deployment role with scoped permissions.

AWS CLI `aws login` obtains temporary credentials using the browser without long-lived access keys. A separate `credential_process` profile bridges those credentials to Terraform and other tools. The profile names must remain distinct. [AWS browser login and credential-process bridge](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html)

```bash
aws login --profile contoso-signin
aws configure set credential_process 'aws configure export-credentials --profile contoso-signin --format process' --profile contoso-lab
aws configure set region eu-central-1 --profile contoso-lab
export AWS_PROFILE=contoso-lab
export AWS_REGION=eu-central-1
export AWS_DEFAULT_REGION="$AWS_REGION"
export AWS_PAGER=""
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
aws sts get-caller-identity
```

When the browser session expires, repeat `aws login --profile contoso-signin`. Do not print or commit exported credentials, login caches or Terraform credentials.

If you already use IAM Identity Center, choose this alternative **instead of** the two-profile bridge:

```bash
aws configure sso --profile contoso-lab
aws sso login --profile contoso-lab
export AWS_PROFILE=contoso-lab
export AWS_REGION=eu-central-1
export AWS_DEFAULT_REGION="$AWS_REGION"
export AWS_PAGER=""
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
aws sts get-caller-identity
```

The SSO wizard needs the access-portal URL, Identity Center Region, account and permission set. Renew this alternative with `aws sso login --profile contoso-lab`. An organization instance is needed for AWS account assignments. **Creating an organization from a free-tier account currently upgrades it to the paid plan and expires its free-tier credits immediately.** Review that consequence before enabling new SSO; an account instance alone does not provide this account-access flow. The repository creates neither account nor organization. [SSO CLI setup](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html), [Identity Center setup and account-plan consequence](https://docs.aws.amazon.com/singlesignon/latest/userguide/enable-identity-center.html)

EKS needs an **IAM user/role ARN**, rather than an STS session ARN. Preserve the complete IAM role path. This handles either an IAM-user session or an assumed-role session:

```bash
CALLER_ARN="$(aws sts get-caller-identity --query Arn --output text)"
ADMIN_PRINCIPAL_ARN=""
case "$CALLER_ARN" in
  arn:aws:iam::*:user/*)
    ADMIN_PRINCIPAL_ARN="$CALLER_ARN"
    ;;
  arn:aws:sts::*:assumed-role/*)
    ROLE_NAME="${CALLER_ARN#*:assumed-role/}"
    ROLE_NAME="${ROLE_NAME%/*}"
    ADMIN_PRINCIPAL_ARN="$(aws iam get-role --role-name "$ROLE_NAME" --query Role.Arn --output text)"
    ;;
  *)
    printf '%s\n' 'Select a non-root IAM deployment user or role before continuing.' >&2
    ;;
esac
printf '%s\n' "$ADMIN_PRINCIPAL_ARN"
```

Do not continue if that variable is empty or contains an STS session/root ARN. Confirm the account is the intended lab account before any apply.

## 2. Create the Terraform state bucket

The `bootstrap/` root uses local state to create an encrypted, versioned, private S3 bucket with TLS-only access. Keep its local state protected; the other roots use separate S3 state keys and native lock files.

```bash
STATE_BUCKET="contoso-tfstate-$(python3 -c 'import uuid; print(uuid.uuid4().hex[:16])')"
cat > bootstrap/terraform.tfvars <<EOF
aws_region = "$AWS_REGION"
state_bucket_name = "$STATE_BUCKET"
EOF
terraform -chdir=bootstrap init
terraform -chdir=bootstrap plan -out=../.local/bootstrap.tfplan
terraform -chdir=bootstrap show ../.local/bootstrap.tfplan
terraform -chdir=bootstrap apply ../.local/bootstrap.tfplan
```

An `apply` of a saved plan executes the reviewed plan directly. Run it only after reviewing its contents. Saved plans, state, outputs and real input files are private and ignored by Git.

Create the two backend files after the bucket exists:

```bash
STATE_BUCKET="$(terraform -chdir=bootstrap output -raw state_bucket_name)"
cat > infra/backend.hcl <<EOF
bucket = "$STATE_BUCKET"
key = "contoso/infra/terraform.tfstate"
region = "$AWS_REGION"
encrypt = true
use_lockfile = true
EOF
cat > platform/backend.hcl <<EOF
bucket = "$STATE_BUCKET"
key = "contoso/platform/terraform.tfstate"
region = "$AWS_REGION"
encrypt = true
use_lockfile = true
EOF
```

The deployment identity needs S3 object access to these keys and their `.tflock` files. Do not delete the bucket before the managed infrastructure is gone.

## 3. Plan and deploy AWS infrastructure

Obtain the public IPv4 address of the workstation that will administer the cluster. This HTTPS request sends an ordinary request to AWS's IP-check endpoint. A VPN/network change may change the address:

```bash
ADMIN_CIDR="$(curl --proto '=https' --tlsv1.2 --fail --silent --show-error https://checkip.amazonaws.com | tr -d '\r\n')/32"
cp infra/terraform.example.tfvars infra/terraform.tfvars
```

Edit `infra/terraform.tfvars` and set:

```hcl
admin_cidrs         = ["YOUR_CURRENT_PUBLIC_IPV4/32"]
admin_principal_arn = "YOUR_EXISTING_IAM_ROLE_ARN"
```

Use the values in `$ADMIN_CIDR` and `$ADMIN_PRINCIPAL_ARN`, set the chosen Region, and review every example value. Keep the restricted API CIDR even if the application later becomes public. Confirm the selected EKS version is available in the chosen Region and in standard support. Resolve an exact PostgreSQL minor before applying:

```bash
aws eks describe-cluster-versions --query 'clusterVersions[].{version:clusterVersion,status:versionStatus}' --output table
aws rds describe-db-engine-versions --engine postgres --query 'DBEngineVersions[?starts_with(EngineVersion, `17.`)].EngineVersion' --output table
```

Set `postgres_engine_version` to the supported exact minor you choose. Instance availability and account quotas also need checking in the target Region. The database defaults to `db.t4g.small` because IAM authentication needs additional memory headroom.

For trusted HTTPS, optionally add these inputs **before** the infrastructure apply:

```hcl
tls_domain_name = "app.example.com" # A subdomain you own
tls_zone_id     = "YOUR_PUBLIC_ROUTE53_HOSTED_ZONE_ID"
```

The public hosted zone and domain delegation must already work. Terraform requests a regional ACM certificate and creates its DNS-validation record; the platform later creates a CNAME to the ALB. Use a subdomain, since this implementation uses a CNAME rather than an apex Alias record. Domain registration/delegation is outside this demo. Without these inputs, the default is source-restricted HTTP with synthetic data, rather than an unverified certificate for the AWS-owned ALB hostname.

```bash
terraform -chdir=infra init -backend-config=backend.hcl
terraform -chdir=infra validate
terraform -chdir=infra plan -out=../.local/infra.tfplan
terraform -chdir=infra show ../.local/infra.tfplan
terraform -chdir=infra apply ../.local/infra.tfplan
terraform -chdir=infra output -json > .local/infra-outputs.json
chmod 600 .local/infra-outputs.json
```

The default enables private API access and restricts the public API endpoint to `admin_cidrs`. Setting `private_only_api=true` requires a connected workstation or an in-VPC runner for the later Helm, Kubernetes and `kubectl` operations. It does not create that connectivity for you.

## 4. Build an immutable application image

The managed node image is x86-64, so explicitly build `linux/amd64`, including from an Apple Silicon Mac. ECR is private; its login token is piped to Docker and is not written to the repository:

```bash
ECR_REPOSITORY="$(terraform -chdir=infra output -raw ecr_repository_url)"
ECR_REGISTRY="${ECR_REPOSITORY%%/*}"
IMAGE_TAG="demo-$(date -u +%Y%m%d%H%M%S)"
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"
docker buildx build --platform linux/amd64 --tag "$ECR_REPOSITORY:$IMAGE_TAG" --push ./app
ECR_NAME="${ECR_REPOSITORY#*/}"
IMAGE_DIGEST="$(aws ecr describe-images --repository-name "$ECR_NAME" --image-ids imageTag="$IMAGE_TAG" --query 'imageDetails[0].imageDigest' --output text)"
APP_IMAGE="$ECR_REPOSITORY@$IMAGE_DIGEST"
printf '%s\n' "$APP_IMAGE"
```

Review image scan findings before using the image. The Kubernetes deployment requires the digest form, so a changed tag cannot silently change the deployed image.

## 5. Deploy the Kubernetes platform

The helper maps known `infra` outputs to platform inputs and writes mode `0600`; it does not call AWS or run Terraform. It refuses to replace an existing file unless `--overwrite` is provided:

```bash
python3 scripts/platform-inputs.py --infra-outputs .local/infra-outputs.json --image "$APP_IMAGE"
terraform -chdir=platform init -backend-config=backend.hcl
terraform -chdir=platform validate
terraform -chdir=platform plan -out=../.local/platform.tfplan
terraform -chdir=platform show ../.local/platform.tfplan
terraform -chdir=platform apply ../.local/platform.tfplan
```

This installs AWS Load Balancer Controller, NetworkPolicies, a separate database-initialization Job, the frontend/API Deployment, Service and Ingress. The initialization role alone can read the RDS-managed master secret. The serving role has `rds-db:connect` for `contoso_app`, with restricted SQL privileges; it cannot fetch that secret. App-to-RDS connections use the actual RDS hostname and bundled AWS CA with `verify-full`.

With a validated HTTPS hostname, you can explicitly widen application access while leaving the API restricted:

```bash
python3 scripts/platform-inputs.py --infra-outputs .local/infra-outputs.json --image "$APP_IMAGE" --ingress-cidr 0.0.0.0/0 --overwrite
terraform -chdir=platform plan -out=../.local/platform-public.tfplan
terraform -chdir=platform show ../.local/platform-public.tfplan
terraform -chdir=platform apply ../.local/platform-public.tfplan
```

The helper and Terraform reject the internet-wide HTTP-only case. Changing inputs regenerates a plan; do not reuse an old plan after editing them.

## 6. Verify the live deployment

Keep this assignment's kubeconfig separate from existing lab contexts. `update-kubeconfig` writes a current context only inside the dedicated file, leaving the normal kubeconfig unchanged. EKS CA verification remains enabled:

```bash
CLUSTER_NAME="$(terraform -chdir=infra output -raw cluster_name)"
LAB_KUBECONFIG="$PWD/.local/kubeconfig"
LAB_CONTEXT="contoso-assignment"
aws eks update-kubeconfig --name "$CLUSTER_NAME" --region "$AWS_REGION" --kubeconfig "$LAB_KUBECONFIG" --alias "$LAB_CONTEXT"
chmod 600 "$LAB_KUBECONFIG"
kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" get nodes
kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" -n contoso get pods,jobs,services,ingresses,networkpolicies
kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" -n contoso rollout status deployment/contoso-app --timeout=5m
APPLICATION_URL="$(terraform -chdir=platform output -raw application_url)"
printf '%s\n' "$APPLICATION_URL"
python3 scripts/verify-live.py --url "$APPLICATION_URL" --write-message
```

Open that URL, add a synthetic message and refresh to verify persistence. The check script uses normal CA and hostname verification for HTTPS and saves one labeled synthetic message when `--write-message` is supplied. Readiness establishes a DB roundtrip, whereas liveness only establishes the HTTP process is alive.

Optionally create and then delete a temporary Job whose Pod lacks the app/bootstrap labels to observe a NetworkPolicy denial:

```bash
python3 scripts/verify-live.py --url "$APPLICATION_URL" --check-networkpolicy --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT"
```

This reuses the deployed application image, requires DNS resolution, and expects DB TCP connection attempts to time out. A failed image pull or unrelated socket error is inconclusive. VPC CNI standard mode can briefly allow traffic before policy programming; the probe waits before attempting connections. It uses a controller-owned Pod because AWS documents unreliable enforcement for standalone Pods. This is a policy check, **not a test that the node SG distinguishes Pods**. Any Pod sharing the allowed node SG may otherwise reach TCP `5432`; IAM and SQL grants supply additional authorization boundaries. [VPC CNI policy considerations](https://docs.aws.amazon.com/eks/latest/userguide/cni-network-policy.html)

Inspect AWS and Kubernetes configuration without retrieving the master secret:

```bash
aws rds describe-db-instances --db-instance-identifier "$CLUSTER_NAME" --query 'DBInstances[0].{public:PubliclyAccessible,multiAZ:MultiAZ,iamAuth:IAMDatabaseAuthenticationEnabled,encrypted:StorageEncrypted,subnets:DBSubnetGroup.Subnets[].SubnetIdentifier,groups:VpcSecurityGroups[].VpcSecurityGroupId}'
DB_SG_ID="$(aws rds describe-db-instances --db-instance-identifier "$CLUSTER_NAME" --query 'DBInstances[0].VpcSecurityGroups[0].VpcSecurityGroupId' --output text)"
aws ec2 describe-security-groups --group-ids "$DB_SG_ID" --query 'SecurityGroups[0].IpPermissions'
kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" -n contoso get serviceaccount contoso-app contoso-bootstrap -o yaml
kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" -n contoso describe ingress contoso-app
```

Also confirm the ALB target group is healthy, the WAF association/rules exist, and the app role cannot read the master secret. IAM policy inspection is not the same as a negative live permission test. Record which checks were actually executed, their results and the deployed commit. [Evidence and interview guide](docs/interview-walkthrough.md)

## Local checks without AWS

Formatting and provider validation can run without an account after provider downloads. Backend-free initialization does not connect to the state bucket:

```bash
terraform fmt -check -recursive
terraform -chdir=bootstrap init -backend=false
terraform -chdir=bootstrap validate
terraform -chdir=bootstrap test
terraform -chdir=infra init -backend=false
terraform -chdir=infra validate
terraform -chdir=infra test
terraform -chdir=platform init -backend=false
terraform -chdir=platform validate
terraform -chdir=platform test
python3 -m py_compile scripts/platform-inputs.py scripts/verify-live.py
python3 -m unittest discover -s scripts -p 'test_*.py'
```

For application tests and local PostgreSQL, follow the application instructions in `app/`. The optional Compose route is:

```bash
docker compose up --build --detach
python3 scripts/verify-live.py --url http://127.0.0.1:18080 --write-message
docker compose down
```

Compose uses local-only passwords and disables DB TLS solely for the isolated local test. It does not emulate RDS IAM, AWS security groups, ALB or WAF. `docker compose down` retains the local database volume; `docker compose down --volumes` deliberately deletes its synthetic data. Do not commit actual output/state/plan files or account details as test evidence.

## Tear down safely

Keep your login credentials valid and retain the controller until its Ingress has been removed. First save the ALB ARN for the deletion waiter, then plan removal of the managed Ingress and any dependent DNS record. Check that the targeted plan keeps the controller running so the Ingress finalizer can clean up AWS resources:

```bash
ALB_HOSTNAME="$(terraform -chdir=platform output -raw alb_hostname)"
ALB_ARN="$(aws elbv2 describe-load-balancers --query "LoadBalancers[?DNSName=='$ALB_HOSTNAME'].LoadBalancerArn | [0]" --output text)"
terraform -chdir=platform plan -destroy -target=kubernetes_ingress_v1.app -out=../.local/ingress-destroy.tfplan
terraform -chdir=platform show ../.local/ingress-destroy.tfplan
terraform -chdir=platform apply ../.local/ingress-destroy.tfplan
aws elbv2 wait load-balancers-deleted --load-balancer-arns "$ALB_ARN"
terraform -chdir=platform plan -destroy -out=../.local/platform-destroy.tfplan
terraform -chdir=platform show ../.local/platform-destroy.tfplan
terraform -chdir=platform apply ../.local/platform-destroy.tfplan
```

This narrowly scoped destroy is an intentional teardown sequence; ordinary updates should use complete plans. If the Ingress/ALB does not disappear, inspect controller logs and its IAM permissions before removing it. Never force-remove a finalizer merely to make the command finish.

The RDS default prevents deletion. Edit `infra/terraform.tfvars` to set `db_deletion_protection=false` and choose snapshot retention deliberately. Keep `db_skip_final_snapshot=false` to retain the final snapshot; set it to `true` only if all data is disposable. The following variable supplies a unique final snapshot identifier to both teardown plans; keep it set through destruction. Review and apply the retention change before destruction:

```bash
export TF_VAR_db_final_snapshot_identifier="${CLUSTER_NAME}-final-$(date -u +%Y%m%d%H%M%S)"
printf '%s\n' "$TF_VAR_db_final_snapshot_identifier" > .local/final-snapshot-id
terraform -chdir=infra plan -out=../.local/cleanup-settings.tfplan
terraform -chdir=infra show ../.local/cleanup-settings.tfplan
terraform -chdir=infra apply ../.local/cleanup-settings.tfplan
```

ECR has `force_delete=false`: a nonempty repository deliberately blocks its deletion. List the images, review that this is the assignment repository, then explicitly remove only the synthetic demo images you intend to discard:

```bash
ECR_NAME="${ECR_REPOSITORY#*/}"
aws ecr list-images --repository-name "$ECR_NAME"
aws ecr batch-delete-image --repository-name "$ECR_NAME" --image-ids imageDigest="$IMAGE_DIGEST"
```

Repeat for any other reviewed demo image digests. Do not delete images needed by another deployment. Then review and apply infrastructure destruction:

```bash
terraform -chdir=infra plan -destroy -out=../.local/infra-destroy.tfplan
terraform -chdir=infra show ../.local/infra-destroy.tfplan
terraform -chdir=infra apply ../.local/infra-destroy.tfplan
```

Check the Region for leftover ALBs, target groups, ENIs, NAT Gateways, EIPs, EBS volumes, RDS resources, snapshots and logs. Retained snapshots and state storage can continue charging. Keep the state bucket and bootstrap state until deletion is confirmed and the desired recovery history is retained. Bucket versioning retains old object versions; destroying application infrastructure does not empty it. [Full retention checklist](docs/cost-and-cleanup.md)

The public repository contains source, synthetic test evidence and the presentation. Assignment correspondence, the source attachment, credentials, state, plans and real deployment inputs are excluded.
