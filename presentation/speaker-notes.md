# Speaker notes

English stakeholder presentation for Contoso. Suggested delivery length follows the assignment: 10–15 minutes.



## 1. Infrastructure as Code for Contoso

Contoso needs a repeatable way to establish and evolve an AWS landing zone. My recommendation is Terraform for the shared infrastructure, with AWS Control Tower providing the multi-account governance baseline. The choice is based on operational ownership as much as syntax. CloudFormation remains a strong AWS-native alternative, and CDK can serve application teams that benefit from a programming language. I will compare those tradeoffs, explain the boundaries between them, and connect the decision to the EKS and database example in this submission. The enterprise landing zone is a proposed operating model. The hands-on repository is a deliberately smaller implementation, and live AWS verification still requires an AWS account.

Sources:
- https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/choose-tool.html



## 2. A landing zone must remain consistent as teams grow

The business problem is consistency as more teams use AWS. A landing zone establishes account structure, access, networking and security foundations. Infrastructure as code gives those choices a versioned definition. A reviewed change can be discussed before it affects a running service. Reusable definitions help teams begin from the same baseline, while repository and state boundaries make responsibility explicit. Recovery also improves because the intended configuration is recorded, although recovery still depends on backups and service-specific procedures. IaC alone does not guarantee security or eliminate drift. Contoso needs named owners, policy checks, controlled execution and follow-up monitoring. These are the outcomes I would use to judge the pilot, rather than choosing a tool only because its syntax is familiar. The benefits here are proposed delivery outcomes, not measured results from an existing Contoso deployment.

Sources:
- https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/choose-tool.html
- https://docs.aws.amazon.com/controltower/latest/userguide/what-is-control-tower.html



## 3. Three authoring models, two deployment engines

This is the main distinction between the tools. Terraform has its own planning and execution engine and talks to services through providers. Its state records the mapping between configuration and managed resources, so the team must choose and operate a backend. CloudFormation takes templates and manages AWS stacks and their state as a service. CDK adds an authoring layer in a supported programming language. It synthesizes CloudFormation templates, which are then deployed through CloudFormation. That means CDK inherits stack lifecycle behavior, and operators still need to understand the generated resources. Terraform is attractive for a platform spanning several providers, while CloudFormation is attractive for an AWS-focused team seeking managed stack state. CDK is especially useful when application teams want tested abstractions in their existing language. The comparison expresses a fit, not an absolute capability boundary.

Sources:
- https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/terraform.html
- https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-stack-templates.html
- https://docs.aws.amazon.com/cdk/v2/guide/home.html
- https://developer.hashicorp.com/terraform/language/state



## 4. Terraform makes the shared platform explicit

For Contoso I would use Terraform to define shared networks, common identity integrations and repeatable workload infrastructure. Modules provide a reusable contract, and a plan makes proposed resource changes visible during review. The benefit of multiple providers is relevant when the platform also integrates Kubernetes, DNS or other services. The cost is operational responsibility. State can contain sensitive information and must be protected, backed up and locked during changes. The platform team also owns provider and module updates, import procedures and recovery from interrupted applies. Prerequisites therefore include HCL and AWS IAM knowledge, dependency management and a reliable backend. I would begin with a small set of maintained modules and document their supported inputs, rather than building a large abstraction framework before the first workload. The recommendation assumes Contoso is willing to operate that workflow.

Sources:
- https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/terraform.html
- https://developer.hashicorp.com/terraform/language/state



## 5. CloudFormation keeps stack operations inside AWS

CloudFormation is a credible alternative for an AWS-only landing zone. AWS operates the stack state, so there is no separate Terraform backend to secure and maintain. Change sets expose proposed updates, StackSets support distribution across accounts and Regions, and rollback behavior helps when a deployment fails. Those protections still require operational understanding. A resource replacement can affect data, and rollback is not a replacement for a database backup. Templates use JSON or YAML, and large stacks need clear boundaries and reuse conventions to remain understandable. The team should know deployment permissions, cross-stack dependencies and how to recover a failed stack. I would prefer CloudFormation if Contoso deliberately standardized on AWS-native operations and placed a high value on managed state. Its suitability is not reduced by its declarative syntax. The choice depends on the team and its surrounding platform.

Sources:
- https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/cloudformation.html
- https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-stack-templates.html



## 6. CDK gives application teams a code-based interface

CDK lets a team describe infrastructure in a supported language and package reusable constructs. It can fit an application team that already tests and reviews code in TypeScript, Python or another supported language. The deployment flow is important: the code synthesizes a CloudFormation template and CloudFormation deploys the stack. Code tests do not prove that a deployment will succeed, and the generated template still needs inspection for permissions and replacements. CDK also adds dependency and toolchain management. Developers need the language prerequisites, Node.js for the shared backend, the CDK CLI and AWS credentials. Each target environment needs bootstrap resources, including asset storage and deployment roles. I would allow CDK for application-owned resources when the team can operate this lifecycle and consumes clear interfaces to shared infrastructure. It should not independently manage the same resources already owned by Terraform.

Sources:
- https://docs.aws.amazon.com/cdk/v2/guide/home.html
- https://docs.aws.amazon.com/cdk/v2/guide/prerequisites.html
- https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html



## 7. Each layer has a single lifecycle owner

The recommendation combines a governance service with an infrastructure workflow. Control Tower establishes and governs the multi-account environment, including controls and centralized oversight. Where Terraform-based account requests are useful, AFT can automate provisioning and account customizations. It requires an existing Control Tower landing zone and a separate AFT management account. AWS explicitly limits AFT to the account provisioning and customization purpose, so the EKS workload is delivered by a separate pipeline. The platform team owns shared foundation modules. Application teams may use Terraform or CDK for resources inside an agreed boundary. One physical resource has one lifecycle owner. Teams exchange identifiers and supported interfaces instead of having several state files or stacks control it. This ownership split is my proposed operating model for Contoso. It needs agreement from security, platform operations and application teams before enterprise adoption.

The central cloud team owns the account and OU model, the logging and audit accounts, and decisions about guardrail exceptions. Terraform must respect resources owned by Control Tower.

Sources:
- https://docs.aws.amazon.com/controltower/latest/userguide/what-is-control-tower.html
- https://docs.aws.amazon.com/controltower/latest/userguide/aft-overview.html
- https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/choose-tool.html



## 8. Delivery combines change review with protected state

The workflow starts with a reviewed Git change. Validation and tests catch errors early, while a plan provides concrete evidence of the proposed infrastructure change. An authorized pipeline applies the reviewed result, then operators inspect service health and drift. For Terraform state, the proposed S3 backend uses encryption, versioning and native S3 lockfile locking. Locking prevents concurrent state writers. It does not validate a change or make an apply transactional. Current HashiCorp guidance deprecates the older DynamoDB locking mechanism, so this submission uses use_lockfile. I would keep state boundaries aligned with owners and lifecycles, with limited access to state and saved plans because they may contain secrets. CI should obtain short-lived credentials through federation. In the hands-on repository, bootstrap, infrastructure and Kubernetes platform are separate roots so the cluster exists before Kubernetes providers connect to it. This is the proposed delivery workflow, not a claim that a remote CI system has already run it.

Sources:
- https://developer.hashicorp.com/terraform/language/backend/s3
- https://developer.hashicorp.com/terraform/language/state



## 9. Private compute and data behind public ingress

This editable diagram connects the recommendation to the assignment implementation. The public Application Load Balancer spans public subnets. It sends application traffic to pods running on EKS managed nodes in private subnets. PostgreSQL runs in an isolated database subnet group, and security groups allow only the required database path. The app uses IAM database authentication over verified TLS. A separate bootstrap role reads the managed master secret to create the application database user, while the steady-state app role does not need that secret. The regional WAF is configurable and enabled by default. Valid browser HTTPS requires an owned DNS name and a matching ACM certificate. An AWS-owned ALB hostname cannot be presented as if a certificate for our own domain covered it. The database subnet group covers two Availability Zones, but the demo database instance itself is single-AZ. AWS connectivity, IAM behavior, ALB routing and live database access still require integration verification after an account is available. This is a design and code demonstration, not evidence of a completed AWS deployment.

Sources:
- https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html
- https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.html

Implementation references in this repository: infra/network.tf, infra/database.tf, infra/identity.tf, platform/ingress.tf and platform/workload.tf.



## 10. A pilot establishes the foundation for wider rollout

The practical submission favors understandable, controlled scope. A single NAT gateway and a single RDS instance reduce the number of resources and recurring costs for a demonstration, but they do not provide full Availability Zone resilience. Production sizing, database Multi-AZ configuration, recovery objectives and backup restoration need explicit decisions. Administrative access should use an appropriate private network path, and internet users need a valid domain and certificate. Operational ownership also includes logs, metrics, patching, budget alerts and drift response. Before wider adoption I would pilot the Terraform foundation in a governed account, perform a reviewed change, verify application to database access, test a recovery procedure and record the outcome. The final decision is Terraform for shared foundations with Control Tower for governance, plus CloudFormation or CDK where a team has a clear and isolated lifecycle boundary. Live AWS checks remain a prerequisite for claiming the hands-on assignment works in AWS.

Sources:
