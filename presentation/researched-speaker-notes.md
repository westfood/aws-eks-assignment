# Contoso landing-zone speaker notes

English narration for the ten-slide Keynote presentation. Scope: how Contoso's central platform team delivers its AWS landing zone through IaC. Workloads are consumers of the foundation; their deployment is outside this presentation. Sources are reference material, not part of the spoken script.

## Slide 1. Delivering Contoso's AWS Landing Zone with IaC

### Spoken script

Contoso is beginning AWS adoption across many departments. The delivery decision is how its central platform team will create and maintain a consistent landing zone. This foundation includes account organization, access, governance, logging and shared networking. Infrastructure as Code records those choices in definitions that can be reviewed and deployed repeatedly. I will compare Terraform, CloudFormation and AWS CDK as delivery tools for that same foundation. My recommendation is CloudFormation as the central team's primary IaC tool, configuring AWS Control Tower through its supported resources and managing additional foundation stacks. Control Tower supplies governance services; it does not replace the delivery tool. This recommendation assumes an AWS-focused landing zone without an established IaC standard. Existing expertise or required integrations could justify a different choice.

### Sources

- [Landing-zone scope](https://docs.aws.amazon.com/prescriptive-guidance/latest/transitioning-to-multiple-aws-accounts/create-landing-zone.html)
- [Control Tower resources delivered through CloudFormation](https://docs.aws.amazon.com/controltower/latest/userguide/creating-resources-with-cloudformation.html)
- [Tool selection and operating model](https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/choose-tool.html)

## Slide 2. Benefits for the Landing-Zone Foundation

### Spoken script

A landing zone will change as Contoso adds departments and adjusts security requirements. Manual setup can leave differences between environments and make it difficult to explain why a setting exists. IaC gives the team a versioned definition of the intended foundation. Reusable templates or modules help apply an agreed baseline consistently. Reviewable changes make proposed updates visible to the people responsible for security and operations. Recorded definitions also support recovery planning and investigation because operators can compare actual configuration with the intended design. These capabilities still require controlled access, backup procedures and clear owners. IaC cannot guarantee a secure design or automatically correct every change made outside the workflow. Contoso should measure consistency, change failures and recovery effort rather than assume a quantified saving from selecting a tool.

### Sources

- [Infrastructure definitions and change tracking](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html)
- [Drift detection and corrective action](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-stack-drift.html)

## Slide 3. Delivery Workflow for Landing-Zone Changes

### Spoken script

The central team proposes a foundation change in Git and records its purpose and owner. Validation and policy checks examine the definitions before a preview exposes the expected resource operations. Security and platform reviewers assess changes to access, controls and shared connectivity. A scoped deployment identity then executes the approved version. After deployment, the team verifies the landing-zone operation, the relevant controls and any drift. A preview helps review; it does not guarantee successful execution or replace understanding service-specific effects. Access controls apply to the repository, approval process and deployment role. Ownership applies to the resources as well: the team must distinguish what its IaC manages directly from what Control Tower manages internally. The same controlled cycle applies whether the authoring tool is Terraform, CloudFormation or CDK.

### Sources

- [Change sets and their limits](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-changesets.html)
- [Control Tower resource ownership](https://docs.aws.amazon.com/controltower/latest/userguide/how-control-tower-works.html)
- [Terraform state-service choices](https://developer.hashicorp.com/terraform/language/state)

## Slide 4. Three IaC Options for the Central Team

### Spoken script

These tools provide different ways to describe and deliver the same landing-zone responsibilities. Terraform uses HCL, its own execution engine and providers that call infrastructure services. It stores the relationship between its definitions and managed resources in state. CloudFormation takes JSON or YAML templates and manages stacks and their state inside AWS. CDK lets the same central team write definitions in a supported programming language and package reusable constructs. Its normal path synthesizes a CloudFormation template and uses CloudFormation for deployment. That is a different authoring experience over the same stack lifecycle. All three can support maintained, reusable definitions. The choice should consider the central team's skills, required service coverage, integrations and operating model, rather than assume that every department needs a different tool.

### Sources

- [Terraform](https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/terraform.html)
- [CloudFormation](https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/cloudformation.html)
- [AWS CDK synthesis and constructs](https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/aws-cdk.html)

## Slide 5. Terraform for Landing-Zone Delivery

### Spoken script

Terraform can express a landing zone as reusable modules covering organization structure, Control Tower configuration and shared services. Its plan supports review before applying changes. It is particularly attractive if Contoso already has a maintained Terraform practice or needs a common workflow across several infrastructure providers. That does not make AWS resource definitions portable to other clouds. State needs an agreed access and recovery model, but Contoso can use managed state through HCP Terraform rather than operate storage itself. The team still owns module and provider updates, permissions and recovery from interrupted changes. A failed apply can leave completed operations in place. Prerequisites include the Terraform CLI, HCL, AWS and IAM knowledge, version control and an execution environment. Nothing in the brief establishes existing Terraform expertise, so that advantage must remain conditional.

### Sources

- [Terraform landing-zone pattern](https://developer.hashicorp.com/validated-patterns/terraform/build-aws-lz-with-terraform)
- [Managed and remote state](https://developer.hashicorp.com/terraform/language/state)
- [Sensitive state and plans](https://developer.hashicorp.com/terraform/language/manage-sensitive-data)
- [Apply failure behavior](https://developer.hashicorp.com/terraform/cli/commands/apply)

## Slide 6. CloudFormation for Landing-Zone Delivery

### Spoken script

CloudFormation can configure Control Tower directly through its LandingZone, EnabledBaseline and EnabledControl resource types. Separate foundation stacks can define other resources the central team owns. This gives Contoso an AWS-native delivery path with managed stack state, reviewable change sets and template reuse through nested stacks or modules. Terraform also offers managed state, so state alone does not decide the choice. CloudFormation's trade-offs include template verbosity, cross-stack dependencies and the need to understand resource updates and replacements. Stack lifecycle management does not guarantee that every underlying service operation can be reversed safely. Prerequisites include JSON or YAML, AWS resource and IAM knowledge, deployment roles and failed-operation procedures. Creating the Control Tower landing zone also requires preparation of organization access, the required service roles and the selected landing-zone configuration.

### Sources

- [Supported Control Tower resource types](https://docs.aws.amazon.com/controltower/latest/userguide/creating-resources-with-cloudformation.html)
- [Landing-zone launch prerequisites](https://docs.aws.amazon.com/controltower/latest/userguide/lz-api-prereques.html)
- [Change-set behavior](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-changesets.html)
- [Reusable nested stacks](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-nested-stacks.html)
- [CloudFormation modules](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/modules-using.html)

## Slide 7. CDK for Landing-Zone Delivery

### Spoken script

CDK is another authoring choice for the central landing-zone team. It can describe supported Control Tower and foundation resources in a programming language, then synthesize the CloudFormation templates that deploy them. Constructs help package reusable patterns, and software tests can check the generated definitions. This fits a team that already maintains infrastructure libraries in a supported language; those skills are not given in the brief. The trade-off is a language toolchain, dependency maintenance and abstraction layers that still require CloudFormation understanding. Tests do not prove that deployment will succeed, and generated permissions and replacements require review. Prerequisites include the chosen language, Node.js tooling, the CDK CLI, AWS credentials and bootstrap preparation for each target environment. CDK remains an alternative for delivering this landing zone, rather than an additional required tool.

### Sources

- [CDK authoring and synthesis](https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/aws-cdk.html)
- [Control Tower baseline construct](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_controltower.CfnEnabledBaseline.html)
- [CDK prerequisites](https://docs.aws.amazon.com/cdk/v2/guide/prerequisites.html)
- [Environment bootstrap](https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html)

## Slide 8. Recommended IaC Approach for Contoso

### Spoken script

I recommend CloudFormation as the primary IaC delivery tool for Contoso's central landing-zone team. It can declare Control Tower configuration and supported governance resources directly, alongside separately owned foundation stacks. Its AWS integration, template reuse and managed stack lifecycle suit the stated AWS-focused scope. Control Tower remains the governance service configured by that code. This is a reasoned default, not a claim that Terraform or CDK cannot deliver a landing zone. Terraform would be preferable if existing skills, maintained modules or required provider integrations changed the operating balance. CDK would be preferable if the central team gained a clear advantage from programming-language constructs. Because the brief gives no existing standard, I would keep one primary delivery workflow and explicit ownership boundaries rather than mandate several authoring tools.

### Sources

- [CloudFormation delivery of Control Tower](https://docs.aws.amazon.com/controltower/latest/userguide/creating-resources-with-cloudformation.html)
- [Launching a landing zone with CloudFormation](https://docs.aws.amazon.com/controltower/latest/userguide/lz-apis-cfn.html)
- [AWS selection criteria](https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/choose-tool.html)

## Slide 9. Landing-Zone Delivery Architecture

### Spoken script

These three steps describe delivery of one AWS landing-zone foundation. First, the platform team records and reviews the landing-zone definitions. Second, CloudFormation executes the approved version using defined deployment roles and change sets. Third, the resulting AWS foundation contains Control Tower's managed governance baseline together with additional shared resources delivered through separate Contoso foundation stacks. Those are distinct ownership domains within the foundation. Control Tower retains lifecycle ownership of its managed implementation resources, while the platform team maintains the configuration and the additional stacks it owns. Security owners define standards and approve policy changes. Account baselines, access, networking and audit arrangements are the delivery scope. This view makes the code, execution mechanism and resulting foundation explicit, with responsibility retained after the initial deployment.

### Sources

- [Control Tower resources through CloudFormation](https://docs.aws.amazon.com/controltower/latest/userguide/creating-resources-with-cloudformation.html)
- [Current organizational choices and managed-resource ownership](https://docs.aws.amazon.com/controltower/latest/userguide/how-control-tower-works.html)
- [Foundation scope](https://docs.aws.amazon.com/prescriptive-guidance/latest/transitioning-to-multiple-aws-accounts/create-landing-zone.html)

## Slide 10. Recommendation, Ownership and Prerequisites

### Spoken script

The recommendation is CloudFormation for delivering Contoso's AWS landing zone, with Control Tower providing the managed governance services configured through that IaC. The platform team owns the repository, templates, deployment identity and change process. Security owners define policy requirements and approve exceptions. Control Tower keeps ownership of its managed implementation resources. Before execution, Contoso needs agreed organization and identity arrangements, suitable management permissions, required service roles and a documented landing-zone configuration. Validation, preview, approval and post-deployment checks apply to future changes as well as initial creation. Terraform and CDK remain credible alternatives if the central team's established skills or integration requirements justify them. For the information given, one AWS-native delivery approach with explicit responsibilities is the clearest recommendation for the shared foundation.

### Sources

- [CloudFormation landing-zone launch and prerequisites](https://docs.aws.amazon.com/controltower/latest/userguide/lz-apis-cfn.html)
- [Required setup](https://docs.aws.amazon.com/controltower/latest/userguide/lz-api-prereques.html)
- [Control Tower ownership](https://docs.aws.amazon.com/controltower/latest/userguide/how-control-tower-works.html)
