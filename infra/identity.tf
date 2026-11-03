data "tls_certificate" "oidc" {
  url = aws_eks_cluster.main.identity[0].oidc[0].issuer
}
resource "aws_iam_openid_connect_provider" "eks" {
  url             = aws_eks_cluster.main.identity[0].oidc[0].issuer
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.oidc.certificates[length(data.tls_certificate.oidc.certificates) - 1].sha1_fingerprint]
}
locals {
  oidc_host = replace(aws_eks_cluster.main.identity[0].oidc[0].issuer, "https://", "")
  service_accounts = {
    cni        = "system:serviceaccount:kube-system:aws-node"
    controller = "system:serviceaccount:kube-system:aws-load-balancer-controller"
    app        = "system:serviceaccount:${local.namespace}:contoso-app"
    bootstrap  = "system:serviceaccount:${local.namespace}:contoso-bootstrap"
  }
}
resource "aws_iam_role" "irsa" {
  for_each = local.service_accounts
  name     = "${var.name}-${each.key}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow", Action = "sts:AssumeRoleWithWebIdentity"
      Principal = { Federated = aws_iam_openid_connect_provider.eks.arn }
      Condition = { StringEquals = {
        "${local.oidc_host}:sub" = each.value
        "${local.oidc_host}:aud" = "sts.amazonaws.com"
      } }
    }]
  })
}
resource "aws_iam_role_policy_attachment" "cni" {
  role       = aws_iam_role.irsa["cni"].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}
# Pinned upstream policy; see policies/README.md for provenance and scope rationale.
resource "aws_iam_policy" "controller" {
  name   = "${var.name}-load-balancer-controller"
  policy = file("${path.module}/policies/aws-load-balancer-controller-v2.14.1.json")
}
resource "aws_iam_role_policy_attachment" "controller" {
  role       = aws_iam_role.irsa["controller"].name
  policy_arn = aws_iam_policy.controller.arn
}
resource "aws_iam_role_policy" "app_database" {
  name = "connect-to-app-database-user"
  role = aws_iam_role.irsa["app"].id
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
  role = aws_iam_role.irsa["bootstrap"].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow", Action = "secretsmanager:GetSecretValue"
      Resource = aws_db_instance.main.master_user_secret[0].secret_arn
    }]
  })
}
