# Interview walkthrough

Use the presentation for the stakeholder discussion. Use this walkthrough for the technical demonstration and follow-up questions. State explicitly whether the environment has been deployed to AWS or only checked locally.

## Explain the purpose

"This demonstration creates a small application platform with separate ingress, compute and database tiers. Terraform owns the desired infrastructure. EKS runs the frontend and API in private compute subnets. PostgreSQL is private and accepts only the configured database traffic. The web page performs a database roundtrip so the demonstration proves more than a load balancer returning a static page."

Show [the architecture](architecture.md) and identify the two AZs, three subnet tiers and the TCP `8080` and `5432` paths. Explain the difference between the application URL and the EKS management endpoint.

## Explain the deployment stages

1. `bootstrap/` creates the protected state bucket.
2. `infra/` creates AWS networking, the EKS cluster and nodes, RDS and IAM roles.
3. Build the application image and push it to the repository used by the deployment.
4. `platform/` installs the controller and application resources. A separate Job initializes database privileges and schema.
5. The controller reconciles the Ingress into an ALB and registers healthy Pod IP targets.

Use the root README's commands. Run and inspect a plan before applying it. Do not pass a database password through command-line flags or publish state/plan files.

## Show the running application

After AWS deployment:

- Inspect EKS node readiness, application Pods and the initialization Job.
- Open the application URL and add a synthetic message.
- Refresh the page and read the saved message. This is a positive DB write/read check, not just a successful TCP connection.
- Inspect `/healthz` and `/readyz`. Explain why only readiness depends on the database.
- Show that the database reports `PubliclyAccessible=false`, is in the database subnet group and has only the intended ingress rule.
- Show the application's service account and the IAM policy granting `rds-db:connect` to its specific DB user/resource. Do not retrieve or print the master secret.

## Explain the security boundaries

"The application needs both network reachability and database authorization. The SG controls TCP reachability. TLS verifies the server. IRSA supplies temporary application identity. IAM DB authentication maps that identity to a database account, and SQL grants limit its operations. These are complementary controls."

The runtime role must fail to retrieve the master secret. A negative DB authorization check should use a separate test service account without the application role. Label network and authorization failures correctly: a missing IAM grant is not evidence that the TCP path is blocked.

An unauthorized network-source test must actually originate outside the allowed DB source group. A test Pod on the same nodes may share the allowed node SG, so it cannot establish that SGs isolate the DB from other Pods.

For WAF, show the ACL association and configured rules. Test from an allowed client address so an ALB CIDR restriction does not mask the result. If HTTPS is configured, use the owned hostname and normal certificate verification. Do not use an insecure TLS client flag as evidence of successful HTTPS.

## Discuss internet exposure

"The public ALB is the entry point. Worker nodes and the database remain private. The ALB terminates HTTPS when a valid ACM certificate is supplied and forwards to healthy application Pod IPs. In the no-domain demo, HTTP is restricted to the explicit demonstration client CIDRs and carries synthetic data."

Explain the alternatives: an internal ALB for internal users, a public ALB for a web application, and private S3 plus CloudFront for a larger static frontend. Choose according to the audience and traffic pattern rather than adding every AWS service.

## Discuss protection

- **ACM and HTTPS:** protect the browser-to-ALB connection with a valid certificate.
- **WAF:** managed request inspection and rate limiting at the ALB.
- **Shield Standard:** baseline AWS DDoS protection; Shield Advanced is a separate paid choice.
- **Security groups and private subnets:** limit network exposure between tiers.
- **IRSA and SQL grants:** limit application identity and database operations.
- **Application authorization:** required for real users and real data; synthetic demonstration messages are not an authenticated product.
- **Logs, alerts, updates and backups:** necessary operational controls beyond the request path.

## Explain a change and teardown

Make a harmless, reviewable change such as adjusting the application replica count. Show the diff, plan and resulting Pods. Keep enough node capacity for any rolling update surge. Avoid changing networking or DB settings purely to make the live demonstration more dramatic.

For teardown, remove the application Ingress while the ALB controller is still running and verify that its AWS resources disappear. Destroy the platform root, then infrastructure. Retain or deliberately remove data snapshots and the state bucket only after the resource inventory and recovery requirements are understood. See [cost and cleanup](cost-and-cleanup.md).

## Be precise about evidence

| Evidence | What it establishes | What it does not establish |
| --- | --- | --- |
| Formatting/schema validation | Terraform can parse configuration against installed provider schemas | AWS authorization or service behavior |
| Mocked Terraform tests | Asserted desired-state relationships and invalid-input rejection | A real plan, routing, quotas or actual cloud resources |
| Local app/PostgreSQL test | Application read/write behavior and local error handling | RDS IAM authentication, RDS TLS, security groups or ALB behavior |
| EKS/RDS live acceptance checks | Observed behavior of the deployed resources at the recorded revision | Future reliability, all possible attack paths or disaster recovery |

When a live check fails, describe its actual output and the next observation you need. The assignment values a clear explanation of decisions, so distinguish a diagnosed problem from a guess.
