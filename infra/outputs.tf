output "environment" { value = var.environment }
output "aws_account_id" { value = var.aws_account_id }
output "region" { value = var.aws_region }
output "cluster_name" { value = aws_eks_cluster.main.name }
output "cluster_endpoint" { value = aws_eks_cluster.main.endpoint }
output "cluster_ca" { value = aws_eks_cluster.main.certificate_authority[0].data }
output "vpc_id" { value = aws_vpc.main.id }
output "public_subnet_ids" { value = [for s in aws_subnet.public : s.id] }
output "public_subnet_cidrs" { value = [for s in aws_subnet.public : s.cidr_block] }
output "database_subnet_cidrs" { value = [for s in aws_subnet.database : s.cidr_block] }
output "database_host" { value = aws_db_instance.main.address }
output "database_name" { value = local.db_name }
output "database_user" { value = local.db_user }
output "bootstrap_secret_arn" { value = aws_db_instance.main.master_user_secret[0].secret_arn }
output "app_role_arn" { value = aws_iam_role.irsa["app"].arn }
output "bootstrap_role_arn" { value = aws_iam_role.irsa["bootstrap"].arn }
output "controller_role_arn" { value = aws_iam_role.irsa["controller"].arn }
output "waf_acl_arn" { value = var.enable_waf ? aws_wafv2_web_acl.main[0].arn : "" }
output "ecr_repository_url" { value = aws_ecr_repository.app.repository_url }
output "admin_cidrs" { value = var.admin_cidrs }
output "resolved_postgres_version" { value = data.aws_rds_engine_version.postgres.version }
output "resolved_addon_versions" {
  value = merge({ "vpc-cni" = data.aws_eks_addon_version.vpc_cni.version }, { for k, v in data.aws_eks_addon_version.other : k => v.version })
}
