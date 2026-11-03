# Decisions and tradeoffs

These decisions define an interview-sized demonstration. They are not a claim that the demo is a complete enterprise landing zone.

| Decision | Reason | Tradeoff or production change |
| --- | --- | --- |
| Terraform for the required deployment | Matches the assignment and makes networking, identity and application infrastructure reviewable in Git | Requires controlled state, provider pinning, review and ownership |
| Three Terraform roots | The state bucket must exist first; Kubernetes providers need an existing cluster | More explicit deployment stages, with separate plans and state keys |
| One VPC in two AZs | Meets EKS subnet requirements and demonstrates separation by tier | Two subnets do not guarantee that every component has an independent standby |
| Private worker nodes | Application nodes do not need public IP addresses | Outbound dependencies need NAT or selected VPC endpoints |
| Isolated DB subnet tier | The DB has neither public access nor a default internet route | Private routing and security groups still need testing |
| RDS PostgreSQL | Managed backups and maintenance; straightforward SQL and a clear port boundary | More hourly cost than a local database; DB engine/version and instance support must be checked in the selected Region |
| Single DB instance in the demo | Keeps the demonstration smaller | Production availability may require Multi-AZ, restore testing and an explicit recovery objective |
| Single NAT Gateway in the demo | Fewer always-on resources | AZ dependency and possible cross-AZ data charges; production may use AZ-local egress |
| ALB IP targets via AWS Load Balancer Controller | Pod target membership follows Kubernetes changes | The controller creates AWS resources asynchronously and has IAM permissions that must be scoped and monitored |
| Frontend and API in one application | Demonstrates an end-to-end DB roundtrip without extra frontend services | A larger static frontend can move to private S3 plus CloudFront |
| DB security group references node SG on TCP 5432 | Avoids allowing a whole VPC CIDR or maintaining node IP lists | Reachability is broader than one Pod; use app IAM authorization now and workload-specific SGs if stronger network isolation is required |
| IRSA for app, initialization and controller roles | Distinct AWS privileges for distinct service accounts | Requires OIDC/STS connectivity and restricted access to node instance metadata |
| IAM DB login for the app | Avoids a long-lived application password in Terraform or Kubernetes | Token generation and DB authentication need supported SDK/engine configurations and DB memory headroom |
| Separate DB initialization Job | Administrative secret access is not part of the serving role | Initialization is another dependency to inspect when deployment fails |
| RDS-managed master secret | Terraform does not generate or output the DB password | Secret rotation and recovery are still operational responsibilities |
| Verified RDS TLS | Checks both encryption and the DB server's identity | CA bundle updates must be deliberate and hostname verification must remain enabled |
| Private EKS API path plus CIDR-restricted public API | Workers use private access while a developer can deploy from an authorized external address | Private-only management requires a VPC-connected runner or workstation |
| Optional real ACM HTTPS | Can provide verified HTTPS when a domain/certificate exists | No assumption that the applicant owns a public domain; restricted HTTP is only the synthetic-data demo fallback |
| WAF option | Demonstrates managed request filtering and rate limiting | Additional cost and rule tuning; WAF is not user authentication |
| No account-wide landing-zone deployment | The enterprise landing zone is the presentation scenario | A real Contoso rollout needs account/OU, identity, audit, networking and recovery requirements before implementation |

## Questions to defend clearly

**Why not just use the database master user in the application?**

The application's job is to read and write demo messages. Schema creation, account administration and secret retrieval belong to an initialization role. Keeping them separate limits the consequences of an application compromise.

**Why not claim the database is isolated from every other Pod?**

The DB security group authorizes the node security group, so network reachability can extend to other Pods on those nodes. The application IAM role and SQL privileges provide additional controls. Per-Pod network identity needs a stronger design, not just a different label in the diagram.

**Why not make the EKS API private-only immediately?**

That is a reasonable production choice when a VPN, connected network or in-VPC deployment runner exists. The demo makes the management path explicit and restricts its public endpoint. It does not pretend that private workload subnets and a private-only management endpoint are the same setting.

**Does a successful mocked Terraform test prove the infrastructure works?**

No. It can establish configuration properties and reject invalid inputs. It does not establish service availability, quotas, IAM authorization, actual routing, controller reconciliation or a successful PostgreSQL connection. The live acceptance checks remain required.

**Why do the API and DB have different health checks?**

Liveness answers whether the process can respond. Readiness checks whether it can serve requests, including a DB connection. A temporary DB outage should remove an unhealthy application target from traffic without necessarily restarting the process continuously.

**What changes before production?**

Establish availability and recovery objectives, add application authentication, enforce HTTPS with owned DNS, implement centralized logs and alerts, test restore procedures, review workload-specific network isolation and use a controlled CI identity. Scale and cost choices then follow measured requirements.
