# Cost and cleanup

Pricing sources checked on **3 November 2026**. An AWS account has not been used to measure this deployment's bill. Prices, credits and service availability must be checked in the selected Region before applying.

Only **dev** is needed for the live presentation. Test and prod have separate account targets and should be costed independently before deployment. Configuration examples do not create resources or imply that all three environments must remain running.

## Cost model

EKS is not automatically a free deployment because the account is new. The control plane has a per-cluster hourly charge, with a higher rate for Kubernetes versions in extended support. EC2 worker instances, their EBS volumes, public IPv4 addresses and data transfer are separate charges. [EKS pricing](https://aws.amazon.com/eks/pricing/)

Prepare an [AWS Pricing Calculator estimate](https://calculator.aws/) using the actual Terraform inputs and the expected time the demo will remain deployed.

| Resource | Quantity/input to check | Metered cost |
| --- | --- | --- |
| EKS control plane | One cluster; confirm selected version is in standard support | Cluster hours |
| EC2 managed worker nodes | Instance type and desired count | Instance hours, burst-credit charges where applicable |
| EBS node storage | Volume size/type for each worker | Provisioned storage and any configured performance |
| NAT Gateway | Single gateway in the demo, or one per AZ if selected | Gateway hours and processed GB |
| Public IPv4 | NAT EIP and public ALB addresses | Address hours |
| ALB | One controller-managed load balancer | Load balancer hours and LCUs |
| RDS PostgreSQL | One instance, storage, backup settings; Multi-AZ if selected | Instance hours, storage, backup/snapshot storage and optional features |
| WAF | Enabled ACL, rules and request volume | ACL/rule charges and inspected requests |
| Secrets Manager | RDS-managed master secret | Secret storage and API usage |
| CloudWatch/ECR/S3 | Logs, application image and Terraform state | Storage, requests, scanning/features and transfer as configured |
| Inspector enhanced ECR scanning | Enabled by the test/prod example scanning policy | Initial scans and applicable re-scans; optional CI Scan API usage is separate |
| Data transfer | Cross-AZ egress, client traffic and image pulls | Applicable transfer charges |

See [VPC/NAT/IPv4](https://aws.amazon.com/vpc/pricing/), [RDS PostgreSQL](https://aws.amazon.com/rds/postgresql/pricing/), [ALB](https://aws.amazon.com/elasticloadbalancing/pricing/), and [WAF pricing](https://aws.amazon.com/waf/pricing/) for the corresponding meters.

The dev demo reduces resource count with a single NAT Gateway and Single-AZ DB; the test/prod examples enable one NAT per AZ and Multi-AZ RDS, with corresponding additional cost. These choices do not provide production egress or DB failover. An RDS subnet group in two AZs does not mean there are two running DB instances. IAM DB authentication requires additional DB memory, so choose an instance with headroom instead of selecting the smallest instance without checking. [IAM DB authentication resource requirements](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.html)

Use an AWS Budget and billing alerts when the account is ready. Budgets notify; they are not a hard spending cap. Keep the account's billing access and root-user security setup separate from the application deployment. Check account-credit terms rather than assuming that a particular service is covered.

Dev's ECR Basic scanning has no additional scan charge, while ordinary repository storage/transfer charges remain. Test/prod examples enable paid Inspector enhanced continuous scanning. Re-scan eligibility and retention settings affect usage: review them before retaining images. Optional GuardDuty Runtime Monitoring and Security Hub CSPM also need a separate cost/scope decision; they are not enabled here. [Basic scanning cost](https://aws.amazon.com/about-aws/whats-new/2024/08/new-version-amazon-ecr-basic-scanning/), [Inspector pricing](https://aws.amazon.com/inspector/pricing/), [GuardDuty pricing](https://aws.amazon.com/guardduty/pricing/), [Security Hub pricing](https://aws.amazon.com/security-hub/pricing/)

## Teardown order

Select the environment explicitly for every cleanup operation. Confirm its account and plan before deletion; dev cleanup must leave test and prod state and resources untouched. Use the environment-targeted commands in the root README and [environment guide](environments.md).

1. Remove the Terraform-managed Ingress while AWS Load Balancer Controller is healthy. Wait for the ALB, target groups and related controller-managed resources to be deleted. The Ingress finalizer should finish while the controller can still call AWS APIs.
2. Destroy the remaining `platform/` resources, including the controller and Kubernetes workloads.
3. Review the database retention decision. The default keeps deletion protection enabled and requires a final snapshot. Set `infra.db_deletion_protection` to `false` in the selected environment JSON file, review the plan and apply that change before destroying the DB. Keep `db_skip_final_snapshot = false` when retaining data; set it to `true` only for deliberately disposable synthetic data. Supply `infra.db_final_snapshot_identifier` with a unique name for this run so it cannot collide with a snapshot from an earlier demo. Set the retention inputs in the selected private environment JSON file so that the same values reach both teardown plans. Record retained snapshot identifiers privately.
4. Review/delete the intended ECR image digests before destroying `infra/`; the repository has `force_delete=false`. Delete a parent manifest index before referenced child images, then review remaining provenance artifacts and other images. Destroying a managed ECR registry scanning configuration resets the entire account/Region to Basic with no rules, rather than restoring an earlier policy. Do not use this state to own a shared policy without coordinating its lifecycle. Platform destroy operations skip the scan gate, so expired findings cannot block teardown. Check for remaining ALBs, target groups, ENIs, NAT Gateways, EIPs, EBS volumes, DB instances, snapshots, secrets and CloudWatch logs in the selected Region. Investigate dependencies rather than repeatedly forcing deletion.
5. Keep the state bucket until infrastructure deletion is complete and the state is backed up. Its version history can contain sensitive infrastructure data. Bucket versioning means deleting current objects does not remove old versions or delete markers.
6. Treat retained RDS snapshots, ECR images, logs, Secrets Manager retention and the state bucket as explicit retained resources. They can continue to incur charges.

Do not destroy the state bucket first: losing state does not delete the resources Terraform managed. Do not delete an ALB controller before it has reconciled the removal of its Ingress resources. Removing a Terraform state entry is also not the same as deleting the AWS resource.

## Record the result

Record the deployed commit, AWS Region, start/end of the live run, acceptance-check results, destroy result and intentionally retained resource categories. Keep real account identifiers and private plan/state files out of the public repository. No deployment or teardown is claimed complete by this document.
