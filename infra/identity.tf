# EKS Pod Identity gives each service account its own IAM role. Unlike IRSA it needs no IAM OIDC
# provider, which AWS-managed projects deny (iam:*Provider*).
locals {
  pod_roles = {
    controller = { namespace = "kube-system", service_account = "aws-load-balancer-controller" }
    app        = { namespace = local.namespace, service_account = "contoso-app" }
    bootstrap  = { namespace = local.namespace, service_account = "contoso-bootstrap" }
  }
}
resource "aws_iam_role" "pod" {
  for_each = local.pod_roles
  name     = "${local.name}-${each.key}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow", Action = ["sts:AssumeRole", "sts:TagSession"]
      Principal = { Service = "pods.eks.amazonaws.com" }
      Condition = {
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
        ArnEquals    = { "aws:SourceArn" = aws_eks_cluster.main.arn }
      }
    }]
  })
}
resource "aws_eks_pod_identity_association" "pod" {
  for_each        = local.pod_roles
  cluster_name    = aws_eks_cluster.main.name
  namespace       = each.value.namespace
  service_account = each.value.service_account
  role_arn        = aws_iam_role.pod[each.key].arn
}
# Pinned upstream policy; see policies/README.md for provenance and scope rationale.
resource "aws_iam_policy" "controller" {
  name   = "${local.name}-load-balancer-controller"
  policy = file("${path.module}/policies/aws-load-balancer-controller-v2.14.1.json")
}
resource "aws_iam_role_policy_attachment" "controller" {
  role       = aws_iam_role.pod["controller"].name
  policy_arn = aws_iam_policy.controller.arn
}
resource "aws_iam_role_policy" "app_database" {
  name = "connect-to-app-database-user"
  role = aws_iam_role.pod["app"].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow", Action = "rds-db:connect"
      Resource = "arn:aws:rds-db:${var.aws_region}:${data.aws_caller_identity.current.account_id}:dbuser:${aws_db_instance.main.resource_id}/${local.db_user}"
    }]
  })
}
resource "aws_iam_role_policy" "bootstrap_secret" {
  name = "read-only-the-database-bootstrap-secret"
  role = aws_iam_role.pod["bootstrap"].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow", Action = "secretsmanager:GetSecretValue"
      Resource = aws_db_instance.main.master_user_secret[0].secret_arn
    }]
  })
}
