data "aws_rds_engine_version" "postgres" {
  engine  = "postgres"
  version = var.postgres_engine_version
  latest  = true
}
resource "aws_security_group" "database" {
  name_prefix = "${var.name}-db-"
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
  name       = "${var.name}-database"
  subnet_ids = [for s in aws_subnet.database : s.id]
}
resource "aws_db_parameter_group" "main" {
  name_prefix = "${var.name}-"
  family      = "postgres${split(".", data.aws_rds_engine_version.postgres.version)[0]}"
  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
  lifecycle { create_before_destroy = true }
}
resource "aws_db_instance" "main" {
  identifier                          = var.name
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
  final_snapshot_identifier           = coalesce(var.db_final_snapshot_identifier, "${var.name}-final")
  enabled_cloudwatch_logs_exports     = ["postgresql", "upgrade"]
  # There is intentionally no password argument or secret value read by Terraform.
}
