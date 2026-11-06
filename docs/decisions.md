# Decisions and trade-offs

| Decision | Why | Trade-off / production change |
| --- | --- | --- |
| Terraform, three roots | The assignment asks for Terraform. The state bucket must exist first, and Kubernetes providers need an existing cluster | Three short apply steps instead of one |
| dev/test/prod as separate AWS accounts | Strongest isolation; matches AWS multi-account guidance | One project per environment in AWS Settings. Only dev exists today |
| mise for tools and environments | One file pins every tool version. `mise -E <env>` selects the account, profile and settings explicitly | Everyone needs mise (CI uses it too) |
| No Terraform workspaces | Separate accounts and state buckets make the boundary visible. A workspace name alone does not | — |
| One VPC, 2 AZs, three subnet tiers | EKS needs 2 AZs; separate tiers show the network boundaries clearly | — |
| RDS PostgreSQL | Managed backups and patching, a clear port boundary | Single-AZ in dev; Multi-AZ in test/prod |
| One NAT gateway in dev | Cost | AZ dependency; test/prod use one per AZ |
| DB SG references the node SG on 5432 | No CIDR-wide rule and no IP lists to maintain | Any Pod on those nodes can reach the port; IAM auth and SQL grants restrict who can log in. Security groups for Pods if needed |
| EKS Pod Identity (not IRSA) | No IAM OIDC provider needed; AWS-managed projects deny creating one. Simpler trust policy | Requires the Pod Identity agent add-on |
| IAM DB auth + separate setup Job | No long-lived app password; admin secret access is limited to a one-time Job | Tokens need 300-1000 MiB of DB memory: `db.t4g.small` by default; dev's Free plan forces micro, so `shared_buffers` is halved there |
| Verified TLS to RDS (`verify-full`) | Checks encryption and the server's identity | CA bundle updates must be deliberate |
| ALB via AWS Load Balancer Controller, IP targets | Standard EKS ingress; targets follow Pods | The controller creates AWS resources; destroy the platform before infra |
| Restricted HTTP by default, optional ACM HTTPS | The demo does not need a domain | Public access (`0.0.0.0/0`) is refused without HTTPS |
| WAF managed rules + rate limit | Cheap, meaningful protection at the edge | Not a replacement for authentication |
| EKS API public endpoint limited to admin IP | Deploy from a laptop without a VPN | Private-only (`private_only_api`) needs a VPC-connected runner |
| Creator is cluster admin | The EKS default; no IAM ARN lookup needed | Add access entries for other admins or CI roles |
| Image tag = hash of the committed files in the image, deployed by digest | Immutable ECR tags; README, test and infra commits reuse the image; the plan fails if it is missing | Commit `app/` changes before building |
| Frontend in the same container | One deployment for the demo | Real frontend: S3 + CloudFront, with `/api` to the ALB |
| Dev is disposable | One-command teardown for a demo with synthetic data | Test/prod keep deletion protection and final snapshots |

## Questions to expect

**Why not let the app use the DB master user?** The app only reads and writes messages. Schema setup and secret access belong to the one-time Job, which limits the damage if the app is compromised.

**Is the DB isolated from every other Pod?** At the network level, no: the rule trusts the node security group. The app's IAM role and SQL grants are the per-workload control. Security groups for Pods would add a network-level boundary.

**Why not a private-only EKS API?** It is the right production choice when a VPN or in-VPC runner exists. For a laptop demo, a public endpoint restricted to one IP is the pragmatic choice, and `private_only_api = true` switches it.

**Do the mocked Terraform tests prove it works?** No. They prove configuration properties and input validation. Only the live smoke test proves routing, IAM and the database connection.

**What changes before production?** HTTPS with a real domain, app authentication, CI with its own deploy role instead of a laptop, alerting and log retention, restore tests, and security groups for Pods if workloads need network separation.
