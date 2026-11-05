# Contoso landing-zone IaC research

Research checked on 5 November 2026. Scope: delivery and ongoing change of Contoso's AWS landing zone by its central platform team. Applications are consumers of the foundation; their deployment is outside the presentation.

## Facts, assumptions and decision

The brief establishes a large enterprise with many applications and departments that has recently begun adopting AWS. It does not establish an existing IaC standard, Terraform expertise, programming-language preference, integration requirements outside AWS, compliance obligations or the expected rate of account requests.

For that stated scope, recommend **CloudFormation as the central team's primary IaC delivery tool**. Use it to declare supported AWS Control Tower landing-zone configuration, baselines and controls, and to deliver separately owned foundation stacks. Control Tower is the managed governance service configured by IaC; it is not a competing authoring tool or a replacement for the delivery workflow. [Supported Control Tower resources](https://docs.aws.amazon.com/controltower/latest/userguide/creating-resources-with-cloudformation.html), [landing-zone delivery with CloudFormation](https://docs.aws.amazon.com/controltower/latest/userguide/lz-apis-cfn.html)

The recommendation assumes an AWS-focused landing zone without an established delivery standard. Its rationale combines direct Control Tower resource support, AWS-native stack lifecycle, reusable templates and an operating model suited to one central team. CloudFormation's included state management is a benefit, but it is not a sufficient reason on its own to reject Terraform: HCP Terraform also provides managed state. This is an architectural recommendation for the information available, not proof that one tool is universally superior. [AWS selection guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/choose-tool.html), [Terraform state-service options](https://developer.hashicorp.com/terraform/language/state)

## IaC benefits for the foundation

Versioned definitions record the intended organization, controls, access and network foundations. Reviewed changes improve traceability; reusable patterns support consistent baseline configuration as departments are added. Operators can compare intended and actual configuration during investigation and recovery. These are capabilities and expected outcomes rather than measured improvements at Contoso. IaC still requires access controls, reviews, policy checks, backup procedures and owners. Infrastructure definitions are not backups of application data. [Infrastructure management and change tracking](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html), [drift detection](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-stack-drift.html)

## Delivery workflow and ownership

The ten-slide presentation places the landing-zone delivery workflow immediately after its business benefits. The central team proposes a versioned change, validates it, previews resource operations and obtains appropriate approval. A scoped deployment identity executes the approved version. Operators then verify the service operation, controls and drift. Repository access, reviewer responsibilities and deployment permissions are explicit throughout. A preview does not guarantee execution success. [Change sets](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-changesets.html)

One resource has one lifecycle owner. The platform team owns its IaC definitions and pipeline. CloudFormation owns the declared stack resources. Control Tower owns the resources it creates internally to implement its managed services; those resources must be changed through supported Control Tower methods. Separate foundation stacks manage only resources assigned to them. Security owners define requirements and approve policy exceptions without creating a second independent lifecycle for the same resources. [Managed-resource boundaries](https://docs.aws.amazon.com/controltower/latest/userguide/how-control-tower-works.html)

## Three alternatives for the same central team

| Tool | Benefits for landing-zone delivery | Trade-offs and prerequisites |
| --- | --- | --- |
| Terraform | Reusable modules, explicit plans, AWS and other providers, existing Terraform practices can be reused | Terraform CLI, HCL, AWS/IAM knowledge, module/provider maintenance and a state access/recovery model, including managed-state options; partial failures need recovery procedures |
| CloudFormation | Supported Control Tower resource types, reusable templates and AWS-managed stack lifecycle, state and change sets | JSON/YAML, AWS/IAM knowledge, deployment roles, careful stack dependencies and replacement review; prepare organization and Control Tower prerequisites |
| AWS CDK | Reusable programming-language constructs, software tests and CloudFormation delivery for the central team's foundation | Programming and CloudFormation skills, Node.js/CDK tooling, dependency maintenance, target-environment bootstrapping and generated-template review |

Terraform uses its own engine and providers. CloudFormation deploys templates as stacks. The standard CDK path synthesizes CloudFormation templates and uses the same stack lifecycle. CDK is therefore an alternative authoring model for this central team, not a separate application-delivery recommendation. [Terraform overview](https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/terraform.html), [CloudFormation overview](https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/cloudformation.html), [CDK model](https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/aws-cdk.html)

### Terraform

Terraform is a credible landing-zone delivery tool even when all resources are on AWS. Existing skills, maintained modules or required provider integrations can make it the preferable choice. Its AWS definitions are not automatically portable to another cloud. State and plans can contain sensitive values; storage can be managed by HCP Terraform or a suitable backend, while the team still governs access and recovery. A failed apply can leave some completed changes in place. [Landing-zone pattern](https://developer.hashicorp.com/validated-patterns/terraform/build-aws-lz-with-terraform), [state](https://developer.hashicorp.com/terraform/language/state), [sensitive data](https://developer.hashicorp.com/terraform/language/manage-sensitive-data), [apply behavior](https://developer.hashicorp.com/terraform/cli/commands/apply)

### CloudFormation

CloudFormation supports `AWS::ControlTower::LandingZone`, `AWS::ControlTower::EnabledBaseline` and `AWS::ControlTower::EnabledControl`. This permits IaC delivery of Control Tower configuration itself, as well as separate additional foundation stacks. Reuse is available through nested stacks and registry modules; CDK is not required for reuse. Change sets and stack-state management do not remove the need to understand replacements and failed service operations. [Control Tower support](https://docs.aws.amazon.com/controltower/latest/userguide/creating-resources-with-cloudformation.html), [nested stacks](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-nested-stacks.html), [modules](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/modules-using.html), [change-set limits](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-changesets.html)

### AWS CDK

CDK can define the same central landing-zone resources through its CloudFormation-backed constructs. The relevant benefit is programmable reuse for the platform team, conditional on its skills. Its dependencies, generated permissions and logical resource identities still need review. The common Node.js toolchain, CDK CLI and language prerequisites apply; each deployment environment requires bootstrap preparation. [Control Tower baseline construct](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_controltower.CfnEnabledBaseline.html), [prerequisites](https://docs.aws.amazon.com/cdk/v2/guide/prerequisites.html), [bootstrapping](https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html)

## Delivery architecture and prerequisites

The proposed architecture has three steps: reviewed IaC definitions for the landing zone, CloudFormation deployment through approved roles and change sets, and the resulting AWS landing-zone foundation. That final target contains both Control Tower's managed baseline implementation and additional shared resources delivered through separate Contoso foundation stacks. These are ownership domains within one foundation, not application-deployment stages. The platform team owns configuration and delivery; security owners define policy standards and approvals. Control Tower retains lifecycle ownership of its managed implementation resources.

Before launch, prepare AWS Organizations management access, the required service roles and an agreed landing-zone manifest/configuration. The AWS CloudFormation launch guide includes preparation of the organization, shared logging/security arrangements and service roles. The concrete prerequisites depend on the selected landing-zone version and integrations. Current Control Tower 4.0 allows organizational choices, including removal of the mandatory Security OU requirement; a fixed account/OU diagram should therefore be labeled a Contoso design choice. [CloudFormation launch prerequisites](https://docs.aws.amazon.com/controltower/latest/userguide/lz-api-prereques.html), [Control Tower structure](https://docs.aws.amazon.com/controltower/latest/userguide/how-control-tower-works.html)

Account Factory for Terraform is optional background, not the recommendation's starting requirement. It needs an existing Control Tower landing zone and a dedicated AFT management account. Its scope is account provisioning and customization, so it does not replace initial landing-zone delivery. [AFT scope](https://docs.aws.amazon.com/controltower/latest/userguide/aft-overview.html)

## Closing recommendation

Recommend CloudFormation for the landing-zone team's IaC delivery, configuring Control Tower and separately owned foundation stacks. Keep one primary workflow and clear platform/security responsibilities. Reconsider Terraform or CDK if established skills, maintained assets or required integrations change the operating balance. No delivery, cost or reliability improvement is claimed to have been measured for Contoso.
