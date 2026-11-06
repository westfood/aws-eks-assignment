data "aws_rds_engine_version" "postgres" {
  engine  = "postgres"
  version = var.postgres_engine_version
  latest  = true
}
resource "aws_security_group" "database" {
  name_prefix = "${local.name}-db-"
  description = "PostgreSQL reachable only from the EKS worker security group"
  vpc_id      = aws_vpc.main.id
}
resource "aws_vpc_security_group_ingress_rule" "database_from_eks" {
  security_group_id            = aws_security_group.database.id
  referenced_security_group_id = aws_security_group.nodes.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  description                  = "EKS workers to PostgreSQL only; app identity is separately restricted by IAM and SQL grants"
}
resource "aws_db_subnet_group" "main" {
  name       = "${local.name}-database"
  subnet_ids = [for s in aws_subnet.database : s.id]
}
resource "aws_db_parameter_group" "main" {
  name_prefix = "${local.name}-"
  family      = "postgres${split(".", data.aws_rds_engine_version.postgres.version)[0]}"
  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
  # On 1 GiB micro instances, give IAM DB auth memory by halving shared_buffers (AWS's advice for burstable classes).
  dynamic "parameter" {
    for_each = endswith(var.db_instance_class, ".micro") ? ["{DBInstanceClassMemory/65536}"] : []
    content {
      name         = "shared_buffers"
      value        = parameter.value
      apply_method = "pending-reboot"
    }
  }
  lifecycle { create_before_destroy = true }
}
# Created here rather than by RDS, so the logs expire and destroy removes the groups (after the instance).
resource "aws_cloudwatch_log_group" "database" {
  for_each          = toset(["postgresql", "upgrade"])
  name              = "/aws/rds/instance/${local.name}/${each.key}"
  retention_in_days = 7
}
resource "aws_db_instance" "main" {
  identifier                          = local.name
  engine                              = "postgres"
  engine_version                      = data.aws_rds_engine_version.postgres.version
  engine_lifecycle_support            = "open-source-rds-extended-support-disabled"
  instance_class                      = var.db_instance_class
  allocated_storage                   = 20
  max_allocated_storage               = 30
  storage_type                        = "gp3"
  storage_encrypted                   = true
  db_name                             = local.db_name
  username                            = "contoso_admin"
  manage_master_user_password         = true
  iam_database_authentication_enabled = true
  db_subnet_group_name                = aws_db_subnet_group.main.name
  parameter_group_name                = aws_db_parameter_group.main.name
  vpc_security_group_ids              = [aws_security_group.database.id]
  publicly_accessible                 = false
  multi_az                            = var.db_multi_az
  backup_retention_period             = 1
  copy_tags_to_snapshot               = true
  auto_minor_version_upgrade          = true
  allow_major_version_upgrade         = false
  apply_immediately                   = false
  deletion_protection                 = var.db_deletion_protection
  skip_final_snapshot                 = var.db_skip_final_snapshot
  final_snapshot_identifier           = coalesce(var.db_final_snapshot_identifier, "${local.name}-final")
  enabled_cloudwatch_logs_exports     = keys(aws_cloudwatch_log_group.database)
  # There is intentionally no password argument or secret value read by Terraform.
}
