# Controller policy provenance

`aws-load-balancer-controller-v2.14.1.json` is the unmodified upstream policy from:

https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.14.1/docs/install/iam_policy.json

This corresponds to Helm chart **1.14.1**, application **v2.14.1**. The controller needs discovery and lifecycle permissions to reconcile ALBs, target groups, security groups and optional WAF associations. Some describe/create actions require wildcard resources. The upstream policy uses resource tags where AWS supports restricting those actions.

The policy is distributed under the upstream [Apache License 2.0](LICENSE), copied from the same release. Copyright remains with its upstream contributors.

Only the `kube-system/aws-load-balancer-controller` service account can assume this role. The application and database bootstrap have separate, narrower roles. Production should additionally review permissions boundaries, organization guardrails and resource conditions for the organization's supported controller features.

Do not replace this policy with a policy for a different controller version without reviewing the changes.
