# Revised deck draft

Draft text for the next Keynote revision. It is still 10 slides and about 950 spoken words: 8 minutes at a calm pace, or 10 with pauses on the diagram slides. That leaves time for questions in a 10–15 minute slot.

What changed compared with the current Keynote deck:

| Current | Revised |
| --- | --- |
| 2 Benefits | 2 **Why now**: the problem and the benefits together, in business terms |
| 3 Delivery workflow | Moved to 9 and merged with the old pipeline slide |
| — | 3 **What we are building**: the account/OU structure (new) |
| 4 Comparison | 4 Comparison, plus rows for multi-account rollout and support |
| 5–7 Tool slides | 5–7 Same layout on all three; 3 pros, 3 cons and prerequisites each |
| 8 Recommendation | 8 Recommendation with **four concrete reasons** and when we'd choose otherwise |
| 9 Pipeline, 10 Recap | 9 How a change flows (workflow + ownership), 10 **Roadmap and decisions needed** (new) |

The speaker notes drop the hedging ("does not guarantee", "not a claim"). Caveats now come up only where they change a decision.

---

## 1. Title

**On slide**

- Delivering Contoso's AWS landing zone
- Infrastructure as Code: options and recommendation
- Rudolf Kreibich, Head of Cloud Engineering | *Itchy Industries ← confirm this name is intended*

**Notes**

Contoso has started using AWS, and many departments will follow. Before they do, they need a shared foundation: accounts, access, security guardrails, logging and networking. In the next ten minutes I'll cover why that foundation should be built as code, compare the three main options (Terraform, CloudFormation and the AWS CDK), and recommend one, with a roadmap for getting the first department live.

---

## 2. Why Infrastructure as Code, and why now

**On slide**

*Without a shared, coded foundation:* every department builds AWS differently, security gaps appear, onboarding is slow, and nobody can show auditors what changed.

| Benefit | What it means for Contoso |
| --- | --- |
| Same standards everywhere | Every new account gets the approved security and logging baseline automatically |
| Faster onboarding | A new department account in hours, not weeks |
| Reviewed changes | Every change is a pull request with a named approver; a full audit trail |
| Recovery | The foundation can be rebuilt from code |
| Less drift | Manual changes are detected and corrected |

**Notes**

The risk at this stage is not technology, it's inconsistency. If each department sets up AWS on its own, Contoso ends up with different security settings, unclear ownership and a slow, manual onboarding process. Infrastructure as Code turns the foundation into reviewed, versioned definitions. The same baseline then applies to every account, a new department gets a ready account quickly, and every change has an author, a reviewer and a history, which is exactly what auditors ask for. Because the foundation is code, it can be rebuilt, and drift from manual changes becomes visible. These benefits are the same whichever tool we pick; the tool decides how much effort they cost.

**Sources:** [What is CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html), [Drift detection](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-stack-drift.html)

---

## 3. What we are building: the landing zone

**On slide**: a diagram (Contoso design choice, not a fixed AWS layout)

```
AWS Organization (Control Tower)
├── Management account          billing, Control Tower, Organizations
├── Security OU
│   ├── Log Archive             central, immutable logs
│   └── Audit                   security tooling, read-only access
├── Infrastructure OU
│   ├── Network                 shared connectivity, egress, DNS
│   └── Shared Services         CI/CD pipeline, artifact registry
├── Workloads OU
│   ├── Department A            dev / test / prod accounts
│   └── Department B            dev / test / prod accounts
└── Sandbox OU                  experiments, spend limits
```

Footer line: *Guardrails (SCPs and Control Tower controls) apply per OU. A new account inherits them on day one.*

**Notes**

This is the structure the code delivers. Control Tower sets up the organization, the central log archive and the audit account. We add an infrastructure OU for shared networking and pipelines, and a workloads OU where each department gets separate dev, test and prod accounts. That separation is the strongest isolation AWS offers, and it's the same model the hands-on demo uses. Guardrails attach to OUs, so when a department gets a new account it inherits the security baseline automatically. The exact OU layout is a Contoso decision; this is a proven starting point.

**Sources:** [Landing-zone scope](https://docs.aws.amazon.com/prescriptive-guidance/latest/transitioning-to-multiple-aws-accounts/create-landing-zone.html), [How Control Tower works](https://docs.aws.amazon.com/controltower/latest/userguide/how-control-tower-works.html)

---

## 4. Three options at a glance

**On slide**: title *Three ways to write it, two engines to run it*

| | Terraform | CloudFormation | AWS CDK |
| --- | --- | --- | --- |
| You write | HCL | YAML / JSON | TypeScript, Python, … |
| Runs on | Terraform + providers | AWS CloudFormation | AWS CloudFormation (generated) |
| State | You run it (S3 or HCP Terraform) | Managed by AWS | Managed by AWS |
| Rolling out to many accounts | Account Factory for Terraform (AFT) | StackSets, Customizations for Control Tower | Via CloudFormation; Landing Zone Accelerator is built on CDK |
| Covers | AWS and other providers | AWS only | AWS only |
| Supported by | HashiCorp / community | AWS Support | AWS (open source) |

**Notes**

All three can build a landing zone; the differences are in what the team writes, what runs it, and what the team has to operate. Terraform has its own engine and works across many providers, but someone has to run its state. CloudFormation is AWS's own service; state and rollback are managed by AWS. The CDK lets engineers write real code, but under the hood it generates CloudFormation, so it's a different way of writing, not a different engine. The row that matters most for a landing zone is the fourth: how a baseline reaches every new account.

**Sources:** [Choosing an IaC tool](https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/choose-tool.html), [Terraform](https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/terraform.html), [CloudFormation](https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/cloudformation.html), [CDK](https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/aws-cdk.html)

---

## 5. Terraform

Use the same layout on slides 5–7: Pros | Cons, then a Prerequisites bar.

**On slide**

| Pros | Cons |
| --- | --- |
| One tool for AWS *and* GitHub, Okta, monitoring… | State to run, lock and protect (or pay for HCP Terraform) |
| Readable plan before every change | Provider upgrades need testing |
| Large module ecosystem; AWS-maintained AFT | Licence changed to BSL in 2023; check terms (OpenTofu is the open fork) |

**Prerequisites:** HCL skills, a state backend with locking, a CI runner, provider version pinning

**Notes**

Terraform's strength is breadth. One workflow can manage AWS together with identity providers, source control and monitoring, and its plan output is easy to review. AWS itself maintains Account Factory for Terraform for account provisioning with Control Tower. The cost is operational: Terraform state must be stored, locked, backed up and access-controlled, or bought as a service. Provider upgrades need testing, and since 2023 Terraform is under the Business Source License, which enterprises usually want legal to review; OpenTofu is the open-source fork. Terraform is the right choice when a team already runs it well.

**Sources:** [Terraform landing-zone pattern](https://developer.hashicorp.com/validated-patterns/terraform/build-aws-lz-with-terraform), [Terraform state](https://developer.hashicorp.com/terraform/language/state), [Account Factory for Terraform](https://docs.aws.amazon.com/controltower/latest/userguide/aft-overview.html)

---

## 6. CloudFormation

**On slide**

| Pros | Cons |
| --- | --- |
| Nothing to operate: AWS stores state and rolls back failed updates | AWS only |
| StackSets push a baseline to every new account in an OU automatically | YAML gets long; limited logic |
| Native to Control Tower (CfCT, Control Tower resource types); AWS Support covers it | Replacements and stuck updates need care |

**Prerequisites:** YAML and AWS/IAM skills, Organizations trusted access for StackSets, a pipeline with linting and policy checks (cfn-lint, cfn-guard)

**Notes**

CloudFormation is AWS's own IaC service, so there is no state for the team to run, and failed updates roll back automatically. For a landing zone the key feature is StackSets: with automatic deployment, a baseline such as logging or security roles appears in every new account the moment it joins an OU. It also plugs directly into Control Tower, through Customizations for Control Tower and native Control Tower resource types, and it's covered by AWS Support. The trade-offs are that it's AWS-only, templates get long, and some updates replace resources, so changes need review.

**Sources:** [StackSets automatic deployment](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-orgs-manage-auto-deployment.html), [Control Tower resources in CloudFormation](https://docs.aws.amazon.com/controltower/latest/userguide/creating-resources-with-cloudformation.html), [Customizations for Control Tower](https://docs.aws.amazon.com/controltower/latest/userguide/automate-customizations.html)

---

## 7. AWS CDK

**On slide**

Small diagram: *Code and constructs → generated CloudFormation → stacks in AWS*

| Pros | Cons |
| --- | --- |
| Real programming language: loops, reuse, unit tests | Two layers to debug: code *and* generated template |
| Deploys through CloudFormation (same engine, same support) | Frequent library updates to keep up with |
| AWS's Landing Zone Accelerator is built on it | Needs software engineers on the platform team |

**Prerequisites:** TypeScript or Python skills, Node.js and the CDK CLI, bootstrap in every account and Region

**Notes**

The CDK suits platform teams that think like software teams. It brings loops, reusable libraries and unit tests, and it still deploys through CloudFormation, so it inherits managed state and AWS support. AWS built its Landing Zone Accelerator on it. The price is an extra layer: when something fails, engineers debug both their code and the generated template, and the libraries move quickly. It's a strong choice once Contoso has a platform team with real development skills.

**Sources:** [CDK](https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/aws-cdk.html), [CDK prerequisites](https://docs.aws.amazon.com/cdk/v2/guide/prerequisites.html), [Bootstrapping](https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html), [Landing Zone Accelerator](https://docs.aws.amazon.com/controltower/latest/userguide/about-lza.html)

---

## 8. Recommendation

**On slide**: title *CloudFormation on Control Tower*

**Why, for Contoso**

1. **Nothing extra to run.** AWS manages state and rollback; AWS Support covers the toolchain.
2. **Built for many accounts.** StackSets roll the baseline out to every new department account automatically.
3. **Native to Control Tower.** It's the path AWS documents and supports for customising it.
4. **Easiest to staff.** YAML plus AWS knowledge; no programming or state-management skills required.

**We'd choose differently if…**

- Contoso already runs Terraform at scale → Terraform + Account Factory for Terraform
- Strict compliance frameworks apply → add Landing Zone Accelerator on top of Control Tower

*Application teams stay free to use Terraform or CDK inside their own accounts.*

**Notes**

My recommendation is CloudFormation, on top of Control Tower. Four reasons. First, Contoso is starting out, so there's no Terraform practice or state infrastructure to reuse, and CloudFormation needs none. Second, a landing zone is a many-accounts problem, and StackSets solve it natively. Third, it's the customisation path AWS documents for Control Tower, so we stay on the supported road. Fourth, it's the easiest to staff. If Contoso already had a strong Terraform team, I'd recommend Terraform with Account Factory for Terraform instead, and if regulators require specific frameworks, Landing Zone Accelerator adds them on top. This decision is for the shared foundation only. Department teams can keep using the tool they know in their own accounts.

**Sources:** [Choosing an IaC tool](https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/choose-tool.html), [Customizing Control Tower](https://docs.aws.amazon.com/controltower/latest/userguide/automate-customizations.html), [Control Tower with LZA](https://docs.aws.amazon.com/controltower/latest/userguide/about-lza.html)

---

## 9. How a change reaches AWS

**On slide**: 5-step flow

```
Pull request → Automated checks → Approval → Pipeline deploys → Monitor
 (Git)          lint, policy,      security     short-lived      drift, Control
                change-set preview for guardrails role          Tower compliance
```

| Who | Owns |
| --- | --- |
| Platform team | Code, pipeline, deployment role, operations |
| Security team | Policies and guardrails; approves changes to them |
| Control Tower | Its own managed resources, changed only through Control Tower |

**Notes**

Every change follows one path. An engineer opens a pull request. Automated checks lint the templates, test them against security policy and show a change-set preview of exactly what will change. Changes to guardrails need security approval. A pipeline, not a person, then deploys with short-lived credentials, and afterwards we watch for drift and for Control Tower compliance findings. Ownership is explicit: the platform team owns the code and pipeline, the security team owns the policies, and Control Tower's own resources are only changed through Control Tower. Nobody clicks changes into production accounts by hand.

**Sources:** [Change sets](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-changesets.html), [Control Tower resource ownership](https://docs.aws.amazon.com/controltower/latest/userguide/how-control-tower-works.html)

---

## 10. Roadmap and decisions needed

**On slide**

| Phase | Outcome |
| --- | --- |
| 1. Foundation | Control Tower, Security OU, central logging, single sign-on |
| 2. Shared services | Network account, pipeline, StackSets baselines |
| 3. Pilot | First department live: dev/test/prod accounts from the pipeline |
| 4. Scale | Remaining departments; add LZA or compliance packs if needed |

**Decisions we need from you**

- Sign off the account and OU structure
- Identity source for single sign-on (for example Entra ID)
- Home Region(s) and data-residency rules
- A platform team owner and 2–3 engineers

**Notes**

Here's how we get there. Phase one sets up Control Tower, the security accounts, central logging and single sign-on. Phase two adds shared networking, the deployment pipeline and the baselines that every account receives. Phase three is the milestone that matters: the first department working in its own dev, test and prod accounts, created entirely from code. Phase four repeats that for the remaining departments. To start, we need four decisions: the account structure, the identity provider, the Regions Contoso is allowed to use, and a small platform team with a clear owner. Thank you; I'm happy to take questions.

**Sources:** [Launching Control Tower with CloudFormation](https://docs.aws.amazon.com/controltower/latest/userguide/lz-apis-cfn.html), [Prerequisites](https://docs.aws.amazon.com/controltower/latest/userguide/lz-api-prereques.html)

---

## Likely questions

**"Your hands-on demo uses Terraform. Why recommend CloudFormation?"**
The assignment asked for Terraform, and for one workload in one account it's an excellent fit. The landing zone is a different job: many accounts, owned by a central team, tightly coupled to Control Tower. For that job CloudFormation and StackSets need less to operate. Departments can keep using Terraform in their own accounts, as the demo does.

**"Why not just Terraform everywhere, for one tool?"**
That's a valid choice if Contoso commits to running Terraform state and pipelines well, and AFT makes it workable with Control Tower. I'd pick it if a Terraform team already exists. Starting from zero, it adds operational work to the critical path.

**"Why not Landing Zone Accelerator straight away?"**
LZA is configuration-driven and aimed at regulated environments. It's a strong option to add on top of Control Tower once compliance requirements are known; it isn't needed to get the first department live.

**"What about OpenTofu?"**
It's the open-source fork of Terraform, compatible with most Terraform code. It removes the licence question but not the state-operation work.

**"How do we stop people changing things by hand?"**
SCPs and Control Tower controls block the risky actions outright, CloudFormation drift detection shows the rest, and production deploy rights belong to the pipeline role, not to people.

**"What does it cost?"**
Control Tower and CloudFormation have no charge of their own. You pay for the services they configure, mainly AWS Config, CloudTrail, log storage and networking, which grow with the number of accounts ([Control Tower pricing](https://docs.aws.amazon.com/controltower/latest/userguide/pricing.html)). The bigger cost is the platform team.
