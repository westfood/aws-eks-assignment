# Contoso EKS demo

Terraform for the hands-on part of the AWS DevOps assignment: a small web app on **EKS** in private subnets, **RDS PostgreSQL** in separate isolated subnets, and only the traffic they need between them. An internet-facing **ALB** with **WAF** exposes the app.

[![Validation](https://github.com/westfood/aws-eks-assignment/actions/workflows/ci.yml/badge.svg)](https://github.com/westfood/aws-eks-assignment/actions/workflows/ci.yml)

![Architecture](docs/architecture.png)

| Assignment item | Where |
| --- | --- |
| Small EKS cluster in a VPC with private subnets | [infra/network.tf](infra/network.tf), [infra/eks.tf](infra/eks.tf): 2 AZs, 2 × `t3.small` managed nodes, no public IPs |
| Database in separate private subnets | [infra/database.tf](infra/database.tf): RDS PostgreSQL 17 in its own subnets with **no internet route** |
| Only necessary traffic between EKS and DB | DB security group allows **TCP 5432 from the EKS node security group only**; IAM DB auth and verified TLS on top |
| Architecture diagram | [docs/architecture.png](docs/architecture.png), editable [draw.io](docs/architecture.drawio) |
| Internet exposure, protection, frontend | [Interview questions](#interview-questions) below |

## Environments

Dev, test and prod are **separate AWS accounts** (separate projects in AWS Settings) built from the same code. Each has its own Terraform state, kubeconfig and settings. **Only dev exists today**; test and prod are ready to fill in when their accounts exist.

| | dev | test | prod |
| --- | --- | --- | --- |
| Settings | [mise.dev.toml](mise.dev.toml) | [mise.test.toml](mise.test.toml) | [mise.prod.toml](mise.prod.toml) |
| AWS profile | `contoso-dev-admin` | `contoso-test-admin` | `contoso-prod-admin` |
| NAT gateway | one (cost) | one per AZ | one per AZ |
| RDS | `db.t4g.micro` (Free plan), Single-AZ, disposable | `db.t4g.small`, Multi-AZ, deletion protection | `db.t4g.small`, Multi-AZ, deletion protection |

Everything runs through mise with an explicit environment: `mise -E dev run <task>`. Without `-E` there is no AWS target, so nothing touches an account by accident. [scripts/tf.sh](scripts/tf.sh) checks that the profile's account matches the environment before Terraform runs, and Terraform checks it again (`allowed_account_ids`).

Region is **eu-north-1**.

## Prerequisites

| | Needed for |
| --- | --- |
| [mise](https://mise.jdx.dev/getting-started.html) | Everything. It installs Terraform, AWS CLI, kubectl, Python and actionlint at the versions pinned in [mise.toml](mise.toml) |
| Docker with Buildx and Compose | [Checks](#checks-no-aws) and building the app image |
| Git | Image tags come from the Git hash of `app/` |
| An AWS project per environment, with profile `contoso-<env>-admin` | Deploying only |

Then, once in the repository:

```bash
mise trust && mise install --locked
```

## Deploy dev

**1. Sign in**

```bash
mise exec -- aws login --profile contoso-dev-admin
```

**2. Account-specific settings** (git-ignored): the dev account ID and your public IP. Your IP is the only address allowed to reach the EKS API and, by default, the app.

```bash
cat > mise.dev.local.toml <<EOF
[env]
TF_VAR_aws_account_id = "$(mise -E dev exec -- aws sts get-caller-identity --query Account --output text)"
TF_VAR_admin_cidrs = '["$(curl -fsS https://checkip.amazonaws.com)/32"]'
EOF
```

**3. Terraform state bucket** (once per account). It's encrypted, versioned and private, named `contoso-dev-tfstate-<account-id>`.

```bash
mise -E dev run tf bootstrap init
mise -E dev run tf bootstrap apply
```

**4. Network, EKS, RDS, ECR, WAF** (about 20 minutes)

```bash
mise -E dev run tf infra init
mise -E dev run tf infra apply
```

**5. App image**: builds the committed `app/` folder for linux/amd64 and pushes it to ECR, tagged with that folder's Git hash. It skips the push if that version is already there.

```bash
mise -E dev run image
```

**6. Kubernetes resources**: AWS Load Balancer Controller, NetworkPolicies, a one-time DB setup Job, the app Deployment and the Ingress that creates the ALB. The plan fails if the current `app/` version's image was not pushed.

```bash
mise -E dev run tf platform init
mise -E dev run tf platform apply
```

**7. Test it**

```bash
mise -E dev run smoke                                   # readiness, write a message, read it back
mise -E dev run kubeconfig                              # writes .kube/dev, leaves ~/.kube/config alone
mise -E dev exec -- kubectl -n contoso get pods,ingress,networkpolicies
mise -E dev run tf platform output -raw application_url # open it, add a message, refresh
```

To show the DB boundary, run `mise -E dev exec -- aws rds describe-db-instances --query 'DBInstances[0].{public:PubliclyAccessible,iamAuth:IAMDatabaseAuthenticationEnabled,sg:VpcSecurityGroups}'`, then show that security group's single inbound rule.

**Optional HTTPS.** If you own a domain in a Route 53 public hosted zone, add `TF_VAR_tls_domain_name = "app.example.com"` and `TF_VAR_tls_zone_id = "Z..."` to `mise.dev.local.toml`, then re-apply infra and platform. That adds an ACM certificate, an HTTP→HTTPS redirect and a DNS record. Only then can the app be opened to everyone with `-var 'ingress_cidrs=["0.0.0.0/0"]'`; Terraform refuses public plain HTTP.

## Interview questions

**How would you expose the application to the internet?** An internet-facing ALB in the public subnets, created by the AWS Load Balancer Controller from a Kubernetes Ingress. It forwards to Pod IPs on port 8080. Nodes and the database never get public addresses. With a domain, add an ACM certificate on the ALB and a Route 53 alias, and redirect HTTP to HTTPS. The EKS API is a separate path, restricted to the admin IP.

**How would you protect it?** In layers:

- **WAF on the ALB:** AWS managed common rules plus a per-IP rate limit.
- **Shield Standard:** baseline DDoS protection, automatic on AWS.
- **TLS** with ACM.
- **Network:** security groups and private/isolated subnets.
- **NetworkPolicies:** default-deny inside the namespace.
- **Least-privilege Pod identities:** the app can only `rds-db:connect` as its own DB user. Only the setup Job can read the master secret.
- **Authentication:** real users still need it at the app level, for example Cognito on the ALB.

**Frontend design.** Today the same container serves a small static page and its JSON API, which keeps the demo to one deployment. The next step for a real frontend is a static build in a private S3 bucket behind **CloudFront** (Origin Access Control). `/api/*` goes to the ALB as a second origin, with WAF on CloudFront. The diagram shows this as a proposal.

More detail: [architecture](docs/architecture.md) and [decisions and trade-offs](docs/decisions.md).

## Tear down dev

Destroy the platform first, so the controller can delete the ALB it created, then the infrastructure. Dev is configured as disposable: the DB is deleted without a final snapshot and ECR is emptied.

```bash
mise -E dev run tf platform destroy
mise -E dev run tf infra destroy
```

The state bucket stays; it costs cents. Test and prod keep deletion protection and final snapshots, so destroying them deliberately takes two steps.

**Cost (rough estimate, eu-north-1):** dev costs about **$0.25–0.30 per hour (~$7 per day)** for the EKS control plane, two nodes, NAT, ALB, RDS and WAF. The project is on the Free plan with $100 credit, so deploy shortly before the interview and destroy it afterwards. Spend is in AWS Settings › Billing.

## Checks (no AWS)

The same checks run locally and in [GitHub Actions](.github/workflows/ci.yml) on every push and pull request: each CI job runs one mise task. Locally, run them all with Docker running:

```bash
mise run check            # all four tasks below, about a minute when cached
docker compose up --build # app + PostgreSQL locally on http://127.0.0.1:18080
```

| Task (CI job) | What it tests |
| --- | --- |
| `lint` (Toolset and lint) | The workflow passes actionlint, mise tasks are valid, `scripts/tf.sh` parses. In CI, also that every tool in `mise.lock` installs on Linux at its pinned version and checksum |
| `app:test` (App tests with PostgreSQL) | 23 app tests, 4 of them against the Compose PostgreSQL 17: write and read back a message, user input stored as literal data (no SQL injection), the app's DB role can't create or delete tables, setup works without a superuser. The rest cover health checks, input validation, error hiding, security headers, enforced TLS to the DB and fresh IAM tokens per connection |
| `app:smoke` (Container smoke test) | Builds the real image, runs it with Docker Compose and PostgreSQL, writes and reads a message over HTTP, and checks the container runs as UID 10001 and can't write to its root filesystem |
| `tf:check` (Terraform) | Formatting, provider lock files and `terraform validate` for all three roots, then 18 tests against mocked AWS and Kubernetes providers: private and isolated subnets, DB reachable only on 5432 from the nodes, encrypted non-public DB, IMDSv2, separate Pod Identity roles, restricted Pod Security, default-deny NetworkPolicies, no public plain HTTP, private encrypted state bucket, and input validation |

What CI can't prove: that AWS accepts the configuration (quotas, permissions, Free plan limits), routing, and IAM login to RDS. Those show up only in a real deployment; `mise -E dev run smoke` checks them end to end.

## Repository layout

| Path | What |
| --- | --- |
| `bootstrap/` | S3 bucket for Terraform state (local state, once per account) |
| `infra/` | VPC, EKS, RDS, ECR, WAF, IAM roles for Pods |
| `platform/` | Load Balancer Controller, app, setup Job, NetworkPolicies, Ingress; reads `infra` outputs from remote state |
| `app/` | Python web app, Dockerfile, tests ([details](app/README.md)) |
| `mise.toml`, `mise.<env>.toml` | Tool versions, tasks, per-environment settings |
| `presentation/` | Part 1: IaC stakeholder presentation |
