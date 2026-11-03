# Sources

Primary technical documentation reviewed on **3 November 2026**. These references support the design and discussion, not a claim that AWS integration has already been tested.

## Development toolchain

- [mise getting started](https://mise.jdx.dev/getting-started.html): project tool configuration, installation, trust and task discovery.
- [mise environment command](https://mise.jdx.dev/cli/env.html): loading the project environment once into the current shell.
- [mise continuous integration](https://mise.jdx.dev/continuous-integration.html): using the project tool configuration in CI.

## Diagram format and icons

- [draw.io AWS libraries](https://www.drawio.com/docs/diagram-types/aws-diagrams/): enabling native AWS shapes, editable diagrams and image export.
- [AWS Architecture Icons](https://aws.amazon.com/architecture/icons/): AWS-approved architecture notation and icon guidance.
- [Official draw.io AWS4 palette](https://github.com/jgraph/drawio/blob/v32.6.1/src/main/webapp/js/diagramly/sidebar/Sidebar-AWS4.js): native AWS shape identifiers and category colors.
- [draw.io Desktop 32.6.1](https://github.com/jgraph/drawio-desktop/releases/tag/v32.6.1): renderer used for the checked-in PNG/SVG exports. Its export CLI uses 1-based page indices.

## Account access

- [AWS CLI browser login and credential-process sharing](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html): temporary development credentials without long-lived access keys, CLI version and sign-in permission requirements.
- [AWS CLI IAM Identity Center setup](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html): alternative SSO profile configuration and renewal.
- [Enable Identity Center](https://docs.aws.amazon.com/singlesignon/latest/userguide/enable-identity-center.html): organization/account-instance scope and the free-tier plan/credit consequence of creating an organization.
- [Root-user guidance](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_root-user.html): separate account setup from routine deployment identity.

## AWS network and EKS

- [EKS VPC and subnet requirements](https://docs.aws.amazon.com/eks/latest/userguide/network-reqs.html): two-AZ subnet requirement, DNS, IP capacity and private-node networking.
- [EKS Kubernetes API endpoint access](https://docs.aws.amazon.com/eks/latest/userguide/cluster-endpoint.html): private access, restricted public access and private-only administration.
- [EKS IAM roles for service accounts](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html): workload identity, trust and instance-metadata caveats.
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

## Cost

- [AWS Pricing Calculator](https://calculator.aws/)
- [EKS pricing](https://aws.amazon.com/eks/pricing/)
- [EC2 On-Demand pricing](https://aws.amazon.com/ec2/pricing/on-demand/)
- [VPC, NAT Gateway and public IPv4 pricing](https://aws.amazon.com/vpc/pricing/)
- [RDS PostgreSQL pricing](https://aws.amazon.com/rds/postgresql/pricing/)
- [Elastic Load Balancing pricing](https://aws.amazon.com/elasticloadbalancing/pricing/)
- [WAF pricing](https://aws.amazon.com/waf/pricing/)
- [Secrets Manager pricing](https://aws.amazon.com/secrets-manager/pricing/)
- [S3 pricing](https://aws.amazon.com/s3/pricing/)
- [AWS Budgets](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html)

No fixed regional total is quoted. A useful estimate must use the final selected Region, instance classes, storage, support tier, traffic, retention settings and actual account credit terms.
