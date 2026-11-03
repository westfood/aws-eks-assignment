# Architecture

This is an implementation design, not evidence of an AWS deployment. The repository can be checked locally before an AWS account exists. The live acceptance checks in the root README are required after deployment.

The diagrams show the **dev account** used for the interview presentation. Test and prod use separate accounts and state, with their configuration differences described in [environment targeting](environments.md).

![Network architecture](architecture.png)

The [draw.io file](architecture.drawio) is the editable source, using native AWS library icons and connectors. It has two pages: **Network and request path** and **Identity and database access**. The [SVG](architecture.svg) and PNG above are exports of the first page. The [Mermaid flow](architecture.mmd) remains a text-based overview.

[Open the published diagram in draw.io](https://app.diagrams.net/?splash=0&libs=aws4#Uhttps%3A%2F%2Fraw.githubusercontent.com%2Fwestfood%2Faws-eks-assignment%2Fmain%2Fdocs%2Farchitecture.drawio), or open the local `.drawio` file in draw.io Desktop. In the browser, you can also choose **Device → Open Existing Diagram** and select the file. To add AWS icons, select **More Shapes → Networking → AWS**, then **Apply**. Shapes, labels, groups and connectors remain editable. Save edits back to `docs/architecture.drawio`, export the previews and commit the updated files.

![Identity and database access](architecture-identity.png)

Export both pages again after editing the source. The helper uses draw.io Desktop, tested with version **32.6.1**; it does not rebuild or overwrite the editable diagram:

```bash
mise run diagrams:export
```

This uses the project's mise-pinned Python after the setup in the root README. draw.io Desktop is a separate optional application. If its executable is not installed on PATH or in the standard macOS Applications folder, set `DRAWIO_BIN` to its location. The helper writes `architecture.svg`, `architecture.png`, `architecture-identity.svg` and `architecture-identity.png`, with the diagram embedded in the exports. You can also export from draw.io using **File → Export as → SVG/PNG**.

## Request path

1. A browser loads the small frontend and calls its same-origin JSON API through an internet-facing Application Load Balancer (ALB).
2. The ALB is attached to public subnets in two Availability Zones. AWS Load Balancer Controller discovers the application Pods as IP targets and sends HTTP traffic to port `8080`. An Ingress is desired state; the controller creates and maintains the AWS load balancer.
3. The application runs on EKS managed worker nodes with private addresses in separate compute subnets. A Kubernetes Service provides stable discovery. The frontend and API share a deployment, so the demo does not need a separate frontend hosting product or cross-origin configuration.
4. The application connects to the private RDS PostgreSQL endpoint on TCP `5432`, using TLS with certificate and hostname verification.

The database subnet group spans two isolated database subnets. The demo uses one DB instance, not a Multi-AZ standby. A subnet group containing two AZs does not itself make the DB highly available. EKS requires cluster subnets in at least two AZs. [EKS subnet requirements](https://docs.aws.amazon.com/eks/latest/userguide/network-reqs.html)

## Subnet and routing boundaries

| Tier | Internet route | Purpose |
| --- | --- | --- |
| Public ingress subnets | Default route to Internet Gateway | ALB and NAT Gateway placement |
| Private compute subnets | Default route through NAT Gateway | EKS nodes, Pods, outbound image pulls and AWS API access |
| Isolated database subnets | No default route to Internet Gateway or NAT | RDS network interfaces |

All tiers remain inside one VPC and can use its local routing. Private placement does not replace security-group controls. The demo's single NAT Gateway lowers the resource count, but creates an AZ dependency and can cause cross-AZ transfer charges. Production should choose AZ-local NAT Gateways or an explicitly designed private-endpoint/central-egress solution.

## Network security

| Flow | Allowed boundary | Why |
| --- | --- | --- |
| Browser to ALB | Configured client CIDRs; listener `80` for the restricted demo, or `443` with a valid ACM certificate | Access the demo |
| ALB to application | ALB backend security-group rules to Pod targets, TCP `8080` | Requests and readiness checks |
| EKS to RDS | DB security-group ingress from the EKS node security group, TCP `5432` | PostgreSQL traffic only |
| Pods to DNS | Cluster DNS, TCP/UDP `53` | Resolve cluster and AWS endpoints |
| Private nodes/Pods to AWS APIs | Required outbound HTTPS through NAT | Image pulls, STS, bootstrap Secrets Manager access |
| Administrator to EKS API | Public endpoint restricted to explicit admin CIDRs, plus IAM/EKS access authorization | Deploy and inspect Kubernetes resources |

The DB rule references a security group instead of a changing list of node IPs. It authorizes network reachability for resources using that group, not individual database users. [RDS security-group behavior](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Overview.RDSSecurityGroups.html)

**Isolation limit:** the node security group can permit TCP `5432` from other Pods on those nodes as well. The application IAM role and restricted PostgreSQL role provide an additional authorization boundary. A NetworkPolicy limiting the demo Pod's egress does not turn a node security group into a per-Pod DB boundary. Workload-specific security groups for Pods are a production improvement when the network boundary must distinguish workloads.

The platform also creates a namespace default-deny NetworkPolicy and specific DNS, ALB-to-application, PostgreSQL and HTTPS egress rules. The VPC CNI add-on has network-policy support enabled. Application/bootstrap PostgreSQL egress is restricted to the database subnet CIDRs, while HTTPS egress remains broad for STS and Secrets Manager. Standard policy mode can briefly allow traffic while a new Pod's policies are programmed; strict mode is not enabled here. The app Service and container both use named port `http` on `8080`, matching the CNI's documented port requirement. These policies need live enforcement checks; their presence in Terraform is not proof of enforcement. Dedicated AWS service endpoints and workload security groups can narrow these paths further. [VPC CNI policy considerations](https://docs.aws.amazon.com/eks/latest/userguide/cni-network-policy.html)

## Identity and database initialization

The long-running application uses a Kubernetes service account bound to an IAM role through IRSA. Its role permits only `rds-db:connect` for the database resource identifier and `contoso_app` database user. It cannot retrieve the master secret. IRSA is application identity, not a network connection. Restrict node instance-metadata access so Pods cannot fall back to the broader node role. [IRSA](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html)

A separate initialization Job uses a different service account and IAM role. It reads the RDS-managed master secret from Secrets Manager, connects over verified TLS, and creates the application schema, table, and restricted IAM-login database role. This separates one-time administrative privileges from the request-serving process. Database passwords are not copied into Terraform variables or Kubernetes Secret resources.

The application signs a fresh IAM authentication token when it opens a new DB connection. The token lasts 15 minutes for authentication; expiration does not end a session already established. SQL privileges still control what the authenticated user can do. IAM DB authentication also consumes DB memory, so the DB instance must have headroom rather than being selected solely by its lowest hourly price. [RDS IAM authentication](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.html)

The client uses the actual RDS hostname and the RDS CA bundle with `sslmode=verify-full`. Encryption without hostname verification would not provide the same server-identity check. [RDS TLS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.SSL.html)

## Management endpoint

Private EKS worker placement is separate from Kubernetes API endpoint exposure. The demo enables the private API path for in-VPC traffic and restricts the public API endpoint to administrator CIDRs. Network access is still followed by IAM authentication and Kubernetes authorization. A private-only API option requires Terraform, Helm and `kubectl` to run from the VPC or a connected network. Merely disabling the public endpoint does not provide that administrative path. [EKS API endpoint options](https://docs.aws.amazon.com/eks/latest/userguide/cluster-endpoint.html)

## HTTP, HTTPS and protection

The basic demo does not assume ownership of a DNS name. Without a certificate, the HTTP ALB listener is restricted to explicit client CIDRs and serves synthetic demonstration data. It is not presented as production HTTPS.

For verified public HTTPS, supply an ACM certificate for a domain you control and point that domain at the ALB. The HTTPS option redirects HTTP to HTTPS. An ACM public certificate cannot simply be requested for an AWS-owned ALB hostname.

When `tls_domain_name` and `tls_zone_id` are supplied to `infra/`, the implementation requests the ACM certificate and creates the validation record in that existing public Route53 zone. The platform root creates the application CNAME after the ALB is provisioned. Domain registration and hosted-zone delegation must already be correct; use a subdomain rather than a zone-apex CNAME.

The regional WAF option, enabled by default, associates managed rules and a rate-based rule with the ALB. WAF filters application requests; it does not replace TLS, application authorization, database access control, or patching. AWS Shield Standard provides the baseline AWS DDoS protection. Shield Advanced is an additional paid option, not a prerequisite for this demo.

## Frontend growth path

The implemented frontend is deliberately small and served by the EKS application. A larger static frontend can use a private S3 origin behind CloudFront with Origin Access Control. Keep the API behind the ALB, define cache behavior deliberately, and add authentication before storing real user data. CloudFront/S3 is a proposed alternative, not a resource that this demo claims to deploy.

## Terraform ownership

| Root | Owns | State |
| --- | --- | --- |
| `bootstrap/` | State bucket configuration | Initially local, retained separately |
| `infra/` | VPC, EKS, RDS, IAM and optional WAF | S3 backend key for infrastructure |
| `platform/` | Kubernetes and Helm resources, including ALB controller and demo workloads | Separate S3 backend key |

Separating `infra` and `platform` avoids configuring Kubernetes/Helm providers against a cluster that has not been created yet. The ALB is created by the controller in response to the Terraform-managed Ingress and must be allowed to disappear before deleting the controller and VPC. S3 state uses encryption, versioning and native S3 locking. State remains sensitive even without database passwords. [Terraform S3 backend](https://developer.hashicorp.com/terraform/language/backend/s3)
