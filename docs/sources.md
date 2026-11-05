# Sources

Primary documentation behind the design, last reviewed 5 November 2026.

## Development toolchain

- [mise getting started](https://mise.jdx.dev/getting-started.html): project tool configuration, installation, trust and task discovery.
- [mise config environments](https://mise.jdx.dev/configuration/environments.html): `mise -E dev` loads `mise.dev.toml` and `mise.dev.local.toml`.
- [mise continuous integration](https://mise.jdx.dev/continuous-integration.html): using the project tool configuration in CI.

## Diagram format and icons

- [draw.io AWS libraries](https://www.drawio.com/docs/diagram-types/aws-diagrams/): enabling native AWS shapes, editable diagrams and image export.
- [AWS Architecture Icons](https://aws.amazon.com/architecture/icons/): AWS-approved architecture notation and icon guidance.
- [Official draw.io AWS4 palette](https://github.com/jgraph/drawio/blob/v32.6.1/src/main/webapp/js/diagramly/sidebar/Sidebar-AWS4.js): native AWS shape identifiers and category colors.
- [draw.io Desktop 32.6.1](https://github.com/jgraph/drawio-desktop/releases/tag/v32.6.1): renderer used for the checked-in PNG/SVG exports. Its export CLI uses 1-based page indices.

## Account access

- [AWS CLI browser login](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html): `aws login` temporary credentials, refreshed by the CLI and SDKs (including Terraform's).
- [Supported services for the new AWS experience](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html): EKS, RDS, ECR, ELB, WAF, ACM and Route 53 are in the Free Tier; Organizations and Identity Center are not.
- [SCPs for projects](https://docs.aws.amazon.com/accounts/latest/reference/scps-and-rcps-for-projects.html): the `iam:*Provider*` deny that rules out IRSA, and the denied Shield API.

## AWS network and EKS

- [EKS VPC and subnet requirements](https://docs.aws.amazon.com/eks/latest/userguide/network-reqs.html): two-AZ subnet requirement, DNS, IP capacity and private-node networking.
- [EKS Kubernetes API endpoint access](https://docs.aws.amazon.com/eks/latest/userguide/cluster-endpoint.html): private access, restricted public access and private-only administration.
- [EKS Pod Identity](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html): per-service-account IAM roles without an OIDC provider; agent address `169.254.170.23`.
- [VPC CNI NetworkPolicy considerations](https://docs.aws.amazon.com/eks/latest/userguide/cni-network-policy.html): controller-owned Pods, Service/container port compatibility and policy-enforcement limits.
- [AWS Load Balancer Controller Ingress annotations](https://kubernetes-sigs.github.io/aws-load-balancer-controller/latest/guide/ingress/annotations/): IP targets, listeners, security groups, health checks, ACM and WAF associations.
- [RDS security groups](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Overview.RDSSecurityGroups.html): allowed sources, ports and source-security-group semantics.

## Database

- [RDS IAM database authentication](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.html): authentication token lifetime, memory requirements, database-user mapping and limitations.
- [RDS TLS and CA bundles](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.SSL.html): encryption and server identity verification.
- [RDS-managed master passwords in Secrets Manager](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-secrets-manager.html): master-secret lifecycle and administrative access.

## Terraform and governance

- [Terraform provider mocking](https://developer.hashicorp.com/terraform/language/tests/mocking): credential-free mock tests and their boundary.
- [Terraform S3 backend](https://developer.hashicorp.com/terraform/language/backend/s3): state, encryption, permissions and S3 lockfile support.
- [AWS Control Tower](https://docs.aws.amazon.com/controltower/latest/userguide/what-is-control-tower.html): managed landing-zone governance.
- [Account Factory for Terraform](https://docs.aws.amazon.com/controltower/latest/userguide/aft-overview.html): Terraform-based account provisioning in a Control Tower environment.
- [AWS CloudFormation concepts](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cfn-whatis-concepts.html): templates, stacks and managed deployment state.
- [AWS CDK concepts](https://docs.aws.amazon.com/cdk/v2/guide/core_concepts.html): constructs, applications, synthesis and CloudFormation.

## Public exposure and protection

- [ACM domain ownership validation](https://docs.aws.amazon.com/acm/latest/userguide/domain-ownership-validation.html): public-certificate prerequisites.
- [AWS WAF](https://docs.aws.amazon.com/waf/latest/developerguide/what-is-aws-waf.html): application request filtering.
- [AWS Shield](https://docs.aws.amazon.com/waf/latest/developerguide/shield-chapter.html): Standard and Advanced protection scopes.
- [CloudFront Origin Access Control for S3](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html): proposed private-origin frontend architecture.
