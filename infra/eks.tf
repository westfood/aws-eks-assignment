resource "aws_iam_role" "cluster" {
  name = "${var.name}-eks"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "eks.amazonaws.com" } }]
  })
}
resource "aws_iam_role_policy_attachment" "cluster" {
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}
resource "aws_cloudwatch_log_group" "eks" {
  name              = "/aws/eks/${var.name}/cluster"
  retention_in_days = 7
}
resource "aws_eks_cluster" "main" {
  name                          = var.name
  role_arn                      = aws_iam_role.cluster.arn
  version                       = var.kubernetes_version
  bootstrap_self_managed_addons = false
  enabled_cluster_log_types     = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
  access_config {
    authentication_mode                         = "API"
    bootstrap_cluster_creator_admin_permissions = false
  }
  upgrade_policy { support_type = "STANDARD" }
  vpc_config {
    subnet_ids              = [for s in aws_subnet.compute : s.id]
    endpoint_private_access = true
    endpoint_public_access  = !var.private_only_api
    public_access_cidrs     = var.private_only_api ? null : var.admin_cidrs
  }
  depends_on = [aws_iam_role_policy_attachment.cluster, aws_cloudwatch_log_group.eks]
}
resource "aws_eks_access_entry" "admin" {
  cluster_name  = aws_eks_cluster.main.name
  principal_arn = var.admin_principal_arn
  type          = "STANDARD"
}
resource "aws_eks_access_policy_association" "admin" {
  cluster_name  = aws_eks_cluster.main.name
  principal_arn = aws_eks_access_entry.admin.principal_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
  access_scope { type = "cluster" }
}
resource "aws_iam_role" "nodes" {
  name = "${var.name}-nodes"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "ec2.amazonaws.com" } }]
  })
}
resource "aws_iam_role_policy_attachment" "nodes" {
  for_each   = toset(["AmazonEKSWorkerNodePolicy", "AmazonEC2ContainerRegistryPullOnly"])
  role       = aws_iam_role.nodes.name
  policy_arn = "arn:aws:iam::aws:policy/${each.value}"
}
# Additional identity shared by these nodes, used only as the DB ingress source.
# The EKS primary security group handles cluster/node communication and ALB backend rules.
resource "aws_security_group" "nodes" {
  name_prefix = "${var.name}-nodes-"
  description = "EKS worker identity used by the database security group"
  vpc_id      = aws_vpc.main.id
}
resource "aws_launch_template" "nodes" {
  name_prefix            = "${var.name}-"
  update_default_version = true
  vpc_security_group_ids = [aws_eks_cluster.main.vpc_config[0].cluster_security_group_id, aws_security_group.nodes.id]
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = 20
      volume_type           = "gp3"
      encrypted             = true
      delete_on_termination = true
    }
  }
  tag_specifications {
    resource_type = "instance"
    tags          = { Name = "${var.name}-worker", Project = var.name, ManagedBy = "terraform" }
  }
}
resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.name}-workers"
  node_role_arn   = aws_iam_role.nodes.arn
  subnet_ids      = [for s in aws_subnet.compute : s.id]
  ami_type        = "AL2023_x86_64_STANDARD"
  capacity_type   = "ON_DEMAND"
  instance_types  = var.node_instance_types
  launch_template {
    id      = aws_launch_template.nodes.id
    version = tostring(aws_launch_template.nodes.latest_version)
  }
  scaling_config {
    desired_size = var.node_count
    min_size     = var.node_count
    max_size     = max(var.node_count, 3)
  }
  update_config { max_unavailable = 1 }
  depends_on = [aws_iam_role_policy_attachment.nodes, aws_eks_addon.vpc_cni]
}
data "aws_eks_addon_version" "vpc_cni" {
  addon_name         = "vpc-cni"
  kubernetes_version = var.kubernetes_version
  most_recent        = true
}
data "aws_eks_addon_version" "other" {
  for_each           = toset(["coredns", "kube-proxy"])
  addon_name         = each.value
  kubernetes_version = var.kubernetes_version
  most_recent        = true
}
resource "aws_eks_addon" "vpc_cni" {
  cluster_name                = aws_eks_cluster.main.name
  addon_name                  = "vpc-cni"
  addon_version               = data.aws_eks_addon_version.vpc_cni.version
  service_account_role_arn    = aws_iam_role.irsa["cni"].arn
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"
  configuration_values        = jsonencode({ enableNetworkPolicy = "true" })
  depends_on                  = [aws_iam_role_policy_attachment.cni]
}
resource "aws_eks_addon" "other" {
  for_each                    = toset(["coredns", "kube-proxy"])
  cluster_name                = aws_eks_cluster.main.name
  addon_name                  = each.value
  addon_version               = data.aws_eks_addon_version.other[each.value].version
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"
  depends_on                  = [aws_eks_node_group.main]
}
