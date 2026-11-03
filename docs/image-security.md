# Container image security

The release path checks the **exact ECR image digest** before generating platform inputs and before a normal platform plan/apply. It queries AWS on every check and blocks High/Critical findings, incomplete scans and unavailable evidence. Destroy operations skip this gate so a vulnerable or deleted image cannot prevent cleanup. This workflow is implemented and tested offline; no live ECR push or scan has been performed yet.

## Scanning policy by environment

| Example target | Configuration | Coverage and cost |
| --- | --- | --- |
| Dev presentation | `BASIC`, `SCAN_ON_PUSH` | Supported OS packages; no additional Basic scanning charge |
| Test and prod | `ENHANCED`, `CONTINUOUS_SCAN` | Amazon Inspector covers OS and language packages, including the application's Python dependencies; Inspector charges apply |

Basic is a low-cost demonstration setting. Enhanced is the stronger recommendation for this application because OS scanning alone does not cover its Python dependencies. Both modes are configurable per account target. A digest and immutable tag identify an artifact; neither proves that it is safe. See [AWS's scanning comparison](https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-scanning.html), [Basic scanning announcement and cost](https://aws.amazon.com/about-aws/whats-new/2024/08/new-version-amazon-ecr-basic-scanning/) and [Enhanced scanning coverage and billing](https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-scanning-enhanced.html).

The Terraform inputs are `infra.ecr_scan_type` and `infra.manage_ecr_registry_scanning`. Public examples explicitly enable registry management for **dedicated assignment accounts**. The underlying variable defaults to `false`: in an account with centrally owned ECR configuration, leave ownership disabled and have its owner supply the required coverage. The gate reads the actual registry and repository settings rather than trusting the requested Terraform value.

**Registry ownership affects the whole account and Region.** Applying the managed configuration replaces that registry's scanning rules. The rule matches the application repository prefix, for example `contoso-dev-app*`. In Enhanced mode, repositories outside matching rules have scanning **Off**; in Basic mode, they use manual scanning. Import and merge an existing policy under its proper owner before enabling management in a shared account. Destroying this Terraform resource resets the registry to **Basic with no rules**; it does not restore its previous settings. [ECR filter behavior](https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-scanning-filters.html), [provider lifecycle behavior](https://github.com/hashicorp/terraform-provider-aws/blob/v6.71.0/website/docs/r/ecr_registry_scanning_configuration.html.markdown)

## Build, scan and release

Follow the root README's [image build commands](../README.md#5-build-push-and-scan-the-dev-application-image). They retain Buildx provenance and select the `linux/amd64` child image manifest when the pushed tag points to an index. The scanner needs the executable image digest; an index or attestation is a different artifact. Inspector documents supported image manifest media types and excludes Docker manifest lists. [Inspector image formats](https://docs.aws.amazon.com/inspector/latest/user/scanning-ecr.html)

```bash
mise run target -- --env dev scan-image --image "$APP_IMAGE"
mise run target -- --env dev platform-inputs --image "$APP_IMAGE"
mise run target -- --env dev terraform platform plan
mise run target -- --env dev terraform platform apply
```

The explicit scan command is useful for inspecting a release decision. Input generation, plan and apply each repeat it, so earlier success is not a cached authorization. Use `--wait-seconds 300` on `scan-image` to select the initial-scan polling budget; AWS CLI request/retry time can extend elapsed time. The helper performs read-only ECR operations and does not silently enable scanning or start a scan.

The gate checks:

- Account, Region, repository and full SHA-256 digest match the selected infrastructure outputs.
- The actual repository is scanned on push or continuously. An Enhanced environment specifically requires Enhanced continuous scanning; Basic targets may accept stronger Enhanced coverage.
- An initial scan has completed. Pending or missing scans are polled for a bounded interval; failed, unsupported, expired or malformed results block the release.
- All finding pages are read. High or Critical severity blocks deployment. Returned suppressed findings are still counted; a suppression is not a release exception.
- On-push evidence is at most **24 hours old**, an explicit project policy covering Basic and any Enhanced on-push coverage accepted by a Basic target. Enhanced continuous coverage is event-driven: the check requires `ACTIVE` status and a completed initial scan, without treating an old initial timestamp alone as stale.

Evidence is written with private permissions to `.local/<environment>/image-scans/<digest-hex>.json`, including target metadata, scan mode/status, timestamps, severity counts and the pass/fail reason. Invalid image identities use `.local/<environment>/image-security.json` as a fallback. These files are ignored by Git. Read findings using `DescribeImageScanFindings`; the newer Basic scanner does not expose scan results through `DescribeImages`. [ECR findings API guidance](https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-scanning.html)

The deployment identity needs `ecr:GetRegistryScanningConfiguration`, `ecr:BatchGetRepositoryScanningConfiguration` and `ecr:DescribeImageScanFindings` for these checks, in addition to existing target validation/deployment permissions. Apply least privilege where each action supports resource restrictions. Registry policy management is a separate deployment permission and ownership decision.

## Respond to a blocked release

Inspect the report and ECR/Inspector finding details. Update the supported base image or locked dependency, rebuild, push a new immutable version, and scan its new digest. A clean result means no policy-blocking known findings were returned at that check; it does not establish absence of malware, application flaws or future CVEs.

For an old Basic scan, explicitly request a fresh scan, then run the gate again:

```bash
mise run target -- --env dev aws ecr start-image-scan \
  --repository-name "$ECR_NAME" --image-id imageDigest="$IMAGE_DIGEST"
mise run target -- --env dev scan-image --image "$APP_IMAGE"
```

Basic allows one scan per image per 24 hours, including its initial scan on push. Enhanced does not support manual image scans: restore coverage/eligibility or push an updated image instead. Check the account's configured Inspector re-scan duration rather than assuming one universal retention window. [Basic scan limits](https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-scanning-basic.html), [Inspector scan eligibility](https://docs.aws.amazon.com/inspector/latest/user/scanning-ecr.html)

There is no bypass flag. A production exception would need reviewed, time-limited risk acceptance, an owner and remediation deadline. Administrators can still bypass a local helper using direct Terraform/Kubernetes access; production enforcement also needs restricted deployment IAM/RBAC and admission policy. Existing non-root execution, read-only filesystem, dropped capabilities and seccomp reduce runtime exposure but do not replace scanning.

## Further AWS-native controls

These are recommendations, **not enabled by this assignment**:

| Control | What it adds | Integration decision |
| --- | --- | --- |
| **ECR managed signing with AWS Signer** | Signs images on push using approved signing profiles | Add verification at EKS admission with Kyverno or Gatekeeper + Ratify, configured trust policy/store and the AWS Signer plugin. Signing alone does not enforce admission. [Managed signing](https://docs.aws.amazon.com/AmazonECR/latest/userguide/managed-signing.html), [EKS verification](https://docs.aws.amazon.com/eks/latest/userguide/image-verification.html) |
| **GuardDuty Runtime Monitoring** | Detects suspicious behavior while workloads run | Supports these EC2-backed EKS nodes via its security agent; it is separately billed and complements static scanning. EKS Fargate and Hybrid Nodes are not supported by this feature. [EKS runtime monitoring](https://docs.aws.amazon.com/guardduty/latest/ug/how-runtime-monitoring-works-eks.html) |
| **Security Hub CSPM and EventBridge** | Central finding triage and notifications when new vulnerabilities appear after release | Configure Inspector integration, cross-account/Region aggregation and alert destinations deliberately. Events do not replace the synchronous release gate. [Security Hub integration](https://docs.aws.amazon.com/inspector/latest/user/securityhub-integration.html), [Inspector events](https://docs.aws.amazon.com/inspector/latest/user/eventbridge-integration.html) |
| **Inspector CI scanning and SBOM Generator** | Earlier checks and a dependency inventory before registry publication | Add a CI step using Inspector Scan API and a CycloneDX SBOM; AWS supplies GitHub Actions and other CI integrations. Requires AWS permissions and paid scan usage. [CI integration](https://docs.aws.amazon.com/inspector/latest/user/scanning-cicd.html) |

For this exercise, prioritize Enhanced coverage for the Python image and notifications for newly discovered High/Critical findings. Signing/admission enforcement is the next supply-chain control; runtime detection addresses a different failure mode. Cost and account-wide scope should be reviewed before enabling optional services.
