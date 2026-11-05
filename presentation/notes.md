# Speaker notes

Companion to [contoso-iac-stakeholder.key](contoso-iac-stakeholder.key): the text on each slide, what to say, sources, and answers to likely questions. About 1,000 spoken words, so 8–10 minutes, which leaves time for questions in a 10–15 minute slot. The same notes are in the deck's presenter notes.

---

## 1. Delivering Contoso's AWS landing zone

**On slide:** Infrastructure as Code: options and recommendation · Rudolf Kreibich, Head of Cloud Engineering | Itchy Industries

**Notes**

Contoso has started using AWS, and many teams will follow. Before they do, they need a shared foundation: accounts, access, security guardrails, logging and networking. In the next ten minutes I'll cover why that foundation should be built as code, compare the three main options (Terraform, CloudFormation and the AWS CDK), and recommend one, with a roadmap for getting the first team live.

---

## 2. One foundation before departments move in

**On slide**

| | |
| --- | --- |
| Consistent baselines | Every new account gets the approved security and logging setup. |
| Faster onboarding | A new application account in hours instead of weeks. |
| Reviewed changes | Every change is a pull request with a named approver. |
| Rebuildable | The whole foundation can be recreated from code. |
| Less drift | Manual changes are detected and corrected. |

*Without it, each department builds AWS its own way: inconsistent security, slow onboarding and no audit trail.*

**Notes**

The risk at this stage is not technology, it's inconsistency. If each department sets up AWS on its own, Contoso ends up with different security settings, unclear ownership and a slow, manual onboarding process. Infrastructure as Code turns the foundation into reviewed, versioned definitions. The same baseline then applies to every account, a new team gets a ready account quickly, and every change has an author, a reviewer and a history, which is exactly what auditors ask for. Because the foundation is code, it can be rebuilt, and drift from manual changes becomes visible. These benefits are the same whichever tool we pick; the tool decides how much effort they cost.

**Sources:** [What is CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html), [Drift detection](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-stack-drift.html)

---

## 3. The landing zone: accounts and guardrails

**On slide**

| | |
| --- | --- |
| Management account | Billing, AWS Organizations and Control Tower |
| Security OU | Log Archive for central logs, Audit for security tooling |
| Infrastructure OU | Network for shared connectivity, Shared Services for CI/CD |
| Workloads OU | Prod and Non-prod OUs; one account per application per environment |
| Sandbox OU | Experiments, with spend limits |

*Guardrails attach to OUs, so a new account inherits them on day one. Each account is a cost unit; Cost Categories roll accounts up to departments, projects and cost centres.*

**Notes**

This is the structure the code delivers. Control Tower sets up the organization, the central log archive and the audit account. We add an infrastructure OU for shared networking and pipelines. Workloads are split into a production and a non-production OU, because that's where the guardrails differ, and every application gets its own account per environment. That follows how work is really organised: by applications and the teams that own them, not by the org chart. It also makes cost tracking simple. AWS bills per account, so every application's cost is exact, and Cost Categories roll accounts up to departments, projects or cost centres. A reorganisation is then a rule change, not an account migration. The exact layout is a Contoso decision; this is AWS's recommended starting point.

**Sources:** [OU best practices](https://aws.amazon.com/blogs/mt/best-practices-for-organizational-units-with-aws-organizations/), [Designing the account structure](https://docs.aws.amazon.com/prescriptive-guidance/latest/designing-control-tower-landing-zone/account-structure.html), [Cost Categories split charges](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/splitcharge-cost-categories.html)

---

## 4. Three ways to write it, two engines to run it

**On slide**

| | Terraform | CloudFormation | AWS CDK |
| --- | --- | --- | --- |
| You write | HCL | YAML / JSON | TypeScript, Python… |
| Runs on | Terraform + providers | AWS CloudFormation | Generated CloudFormation |
| State | You run it | Managed by AWS | Managed by AWS |
| Many accounts | Account Factory (AFT) | StackSets, CfCT | Via CloudFormation; LZA |
| Covers | AWS + other providers | AWS only | AWS only |
| Support | HashiCorp, community | AWS Support | AWS, open source |

**Notes**

All three can build a landing zone; the differences are in what the team writes, what runs it, and what the team has to operate. Terraform has its own engine and works across many providers, but someone has to run its state. CloudFormation is AWS's own service; state and rollback are managed by AWS. The CDK lets engineers write real code, but under the hood it generates CloudFormation, so it's a different way of writing, not a different engine. The row that matters most for a landing zone is "many accounts": how a baseline reaches every new account.

**Sources:** [Choosing an IaC tool](https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/choose-tool.html), [Terraform](https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/terraform.html), [CloudFormation](https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/cloudformation.html), [CDK](https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/aws-cdk.html)

---

## 5. Terraform: one tool across providers

**On slide**

| Pros | Cons |
| --- | --- |
| One workflow for AWS and other tools | State to run, lock and protect |
| Readable plan before every change | Provider upgrades need testing |
| Large module ecosystem; AWS-built AFT | BSL licence since 2023 (OpenTofu fork) |

**Prerequisites:** HCL skills, a state backend with locking, a CI runner and pinned provider versions

**Notes**

Terraform's strength is breadth. One workflow can manage AWS together with identity providers, source control and monitoring, and its plan output is easy to review. AWS itself maintains Account Factory for Terraform for account provisioning with Control Tower. The cost is operational: Terraform state must be stored, locked, backed up and access-controlled, or bought as a service. Provider upgrades need testing, and since 2023 Terraform is under the Business Source License, which enterprises usually want legal to review; OpenTofu is the open-source fork. Terraform is the right choice when a team already runs it well.

**Sources:** [Terraform landing-zone pattern](https://developer.hashicorp.com/validated-patterns/terraform/build-aws-lz-with-terraform), [Terraform state](https://developer.hashicorp.com/terraform/language/state), [Account Factory for Terraform](https://docs.aws.amazon.com/controltower/latest/userguide/aft-overview.html)

---

## 6. CloudFormation: nothing extra to operate

**On slide**

| Pros | Cons |
| --- | --- |
| Nothing to operate: AWS runs state | AWS only |
| StackSets reach every new account | Long YAML, limited logic |
| Native to Control Tower; AWS Support | Replacements need careful review |

**Prerequisites:** YAML and AWS / IAM skills, StackSets trusted access, a pipeline with cfn-lint and cfn-guard checks

**Notes**

CloudFormation is AWS's own IaC service, so there is no state for the team to run, and failed updates roll back automatically. For a landing zone the key feature is StackSets: with automatic deployment, a baseline such as logging or security roles appears in every new account the moment it joins an OU. It also plugs directly into Control Tower, through Customizations for Control Tower and native Control Tower resource types, and it's covered by AWS Support. The trade-offs are that it's AWS-only, templates get long, and some updates replace resources, so changes need review.

**Sources:** [StackSets automatic deployment](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-orgs-manage-auto-deployment.html), [Control Tower resources in CloudFormation](https://docs.aws.amazon.com/controltower/latest/userguide/creating-resources-with-cloudformation.html), [Customizations for Control Tower](https://docs.aws.amazon.com/controltower/latest/userguide/automate-customizations.html)

---

## 7. CDK: infrastructure as real code

**On slide:** *Platform code and constructs → Synthesized CloudFormation → Landing-zone stacks and resources*

| Pros | Cons |
| --- | --- |
| Loops, reuse and unit tests in code | Two layers to debug: code + template |
| Deploys through CloudFormation | Fast-moving library updates |
| AWS built Landing Zone Accelerator on it | Needs software engineers |

**Prerequisites:** TypeScript or Python skills, Node.js and the CDK CLI, bootstrap in every account and Region

**Notes**

The CDK suits platform teams that think like software teams. It brings loops, reusable libraries and unit tests, and it still deploys through CloudFormation, so it inherits managed state and AWS support. AWS built its Landing Zone Accelerator on it. The price is an extra layer: when something fails, engineers debug both their code and the generated template, and the libraries move quickly. It's a strong choice once Contoso has a platform team with real development skills.

**Sources:** [CDK](https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/aws-cdk.html), [CDK prerequisites](https://docs.aws.amazon.com/cdk/v2/guide/prerequisites.html), [Bootstrapping](https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html), [Landing Zone Accelerator](https://docs.aws.amazon.com/controltower/latest/userguide/about-lza.html)

---

## 8. CloudFormation on Control Tower

**On slide**

| | | |
| --- | --- | --- |
| Nothing to run | AWS runs state and rollback | AWS Support covers it |
| Many accounts | StackSets reach new accounts | Automatically, per OU |
| Control Tower fit | AWS's documented path | CfCT and CT resources |
| Easy to staff | YAML plus AWS knowledge | No state or code skills |

*Otherwise: Terraform + AFT if a strong Terraform team exists; add LZA for strict compliance. Application teams keep their own tools.*

**Notes**

My recommendation is CloudFormation, on top of Control Tower. Four reasons. First, Contoso is starting out, so there's no Terraform practice or state infrastructure to reuse, and CloudFormation needs none. Second, with one account per application per environment, a landing zone is a many-accounts problem, and StackSets solve it natively. Third, it's the customisation path AWS documents for Control Tower, so we stay on the supported road. Fourth, it's the easiest to staff. If Contoso already had a strong Terraform team, I'd recommend Terraform with Account Factory for Terraform instead, and if regulators require specific frameworks, Landing Zone Accelerator adds them on top. This decision is for the shared foundation only. Application teams can keep using the tool they know in their own accounts.

**Sources:** [Choosing an IaC tool](https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/choose-tool.html), [Customizing Control Tower](https://docs.aws.amazon.com/controltower/latest/userguide/automate-customizations.html), [Control Tower with LZA](https://docs.aws.amazon.com/controltower/latest/userguide/about-lza.html)

---

## 9. How a change reaches AWS

**On slide:** *Pull request in Git → Checks and preview → Approval for guardrails → Pipeline deploys, then drift check*

| Who owns what | Controlled access |
| --- | --- |
| Platform: code, pipeline, operations | Pipeline deploys, not people |
| Security: policies and guardrails | Short-lived deployment credentials |
| Control Tower: its own resources | Security approves guardrail changes |

**Notes**

Every change follows one path. An engineer opens a pull request. Automated checks lint the templates, test them against security policy and show a change-set preview of exactly what will change. Changes to guardrails need security approval. A pipeline, not a person, then deploys with short-lived credentials, and afterwards we watch for drift and for Control Tower compliance findings. Ownership is explicit: the platform team owns the code and pipeline, the security team owns the policies, and Control Tower's own resources are only changed through Control Tower. Nobody clicks changes into production accounts by hand.

**Sources:** [Change sets](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-changesets.html), [Control Tower resource ownership](https://docs.aws.amazon.com/controltower/latest/userguide/how-control-tower-works.html)

---

## 10. Roadmap and decisions needed

**On slide**

| Roadmap | Decisions needed |
| --- | --- |
| 1. Foundation: Control Tower, SSO, logs | Account and OU structure |
| 2. Shared services: network, pipeline | Cost allocation: tags, cost categories |
| 3. Pilot: first application team live | Identity source for SSO |
| 4. Scale: onboard remaining teams | Regions and data residency |
| | Platform owner + 2–3 engineers |

**Milestone:** First application live in its own non-prod and prod accounts, created entirely from code.

**Notes**

Here's how we get there. Phase one sets up Control Tower, the security accounts, central logging and single sign-on. Phase two adds shared networking, the deployment pipeline and the baselines that every account receives. Phase three is the milestone that matters: the first application team working in its own non-prod and prod accounts, created entirely from code. Phase four repeats that for the remaining teams. To start, we need five decisions: the account structure, how costs are allocated to departments and projects, the identity provider, the Regions Contoso is allowed to use, and a small platform team with a clear owner. Thank you; I'm happy to take questions.

**Sources:** [Launching Control Tower with CloudFormation](https://docs.aws.amazon.com/controltower/latest/userguide/lz-apis-cfn.html), [Prerequisites](https://docs.aws.amazon.com/controltower/latest/userguide/lz-api-prereques.html)

---

## Likely questions

**"Your hands-on demo uses Terraform. Why recommend CloudFormation?"**
The assignment asked for Terraform, and for one workload in one account it's an excellent fit. The landing zone is a different job: many accounts, owned by a central team, tightly coupled to Control Tower. For that job CloudFormation and StackSets need less to operate. Application teams can keep using Terraform in their own accounts, as the demo does.

**"How do departments see and pay for their costs?"**
Through attributes, not structure. Each account is tagged with its owner, cost centre and project, and AWS Cost Categories roll accounts up into departments or projects. Shared costs such as networking and logging are split across them with split charge rules: evenly, by percentage, or in proportion to usage. A project that spans departments, or a reorganisation, is a rule change; no account has to move.

**"Isn't one account per application per environment a lot of accounts?"**
Yes, and that's intended: accounts are AWS's strongest isolation and cleanest cost boundary, and they cost nothing in themselves. It only works if creating an account is automated, which is why Account Factory and StackSets are part of the recommendation. Small applications can share a non-prod account.

**"Why not just Terraform everywhere, for one tool?"**
That's a valid choice if Contoso commits to running Terraform state and pipelines well, and AFT makes it workable with Control Tower. I'd pick it if a Terraform team already exists. Starting from zero, it adds operational work to the critical path.

**"Why not Landing Zone Accelerator straight away?"**
LZA is configuration-driven and aimed at regulated environments. It's a strong option to add on top of Control Tower once compliance requirements are known; it isn't needed to get the first team live.

**"What about OpenTofu?"**
It's the open-source fork of Terraform, compatible with most Terraform code. It removes the licence question but not the state-operation work.

**"How do we stop people changing things by hand?"**
SCPs and Control Tower controls block the risky actions outright, CloudFormation drift detection shows the rest, and production deploy rights belong to the pipeline role, not to people.

**"What does it cost?"**
Control Tower and CloudFormation have no charge of their own. You pay for the services they configure, mainly AWS Config, CloudTrail, log storage and networking, which grow with the number of accounts ([Control Tower pricing](https://docs.aws.amazon.com/controltower/latest/userguide/pricing.html)). The bigger cost is the platform team.
