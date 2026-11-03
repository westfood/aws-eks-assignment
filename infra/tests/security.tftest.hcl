mock_provider "aws" {
  override_during = plan
  mock_data "aws_availability_zones" { defaults = { names = ["eu-central-1a", "eu-central-1b", "eu-central-1c"] } }
  mock_data "aws_caller_identity" { defaults = { account_id = "123456789012" } }
  mock_data "aws_eks_addon_version" { defaults = { version = "v1.20.4-eksbuild.1" } }
  mock_resource "aws_eks_cluster" {
    defaults = {
      identity              = [{ oidc = [{ issuer = "https://oidc.eks.eu-central-1.amazonaws.com/id/EXAMPLE" }] }]
      certificate_authority = [{ data = "dGVzdC1jYQ==" }]
    }
  }
  mock_resource "aws_db_instance" {
    defaults = {
      resource_id        = "db-ABCDEFGHIJKLMNOPQRSTU12345"
      master_user_secret = [{ secret_arn = "arn:aws:secretsmanager:eu-central-1:123456789012:secret:rds-example", kms_key_id = "example", secret_status = "active" }]
    }
  }
}
mock_provider "tls" {
  mock_data "tls_certificate" {
    defaults = { certificates = [{ sha1_fingerprint = "0123456789012345678901234567890123456789" }] }
  }
}
override_data {
  target = data.aws_rds_engine_version.postgres
  values = { version = "17.6" }
}
variables {
  environment         = "dev"
  aws_account_id      = "123456789012"
  admin_cidrs         = ["203.0.113.10/32"]
  admin_principal_arn = "arn:aws:iam::123456789012:role/example-admin"
}
run "private_tiers_and_minimum_database_access" {
  command = plan
  assert {
    condition     = aws_eks_cluster.main.name == "contoso-dev" && aws_db_instance.main.identifier == "contoso-dev" && aws_ecr_repository.app.name == "contoso-dev-app"
    error_message = "Dev resource names must be explicitly environment-qualified."
  }
  assert {
    condition     = length(aws_subnet.compute) == 2 && length(aws_subnet.database) == 2 && alltrue([for s in aws_subnet.compute : !s.map_public_ip_on_launch]) && alltrue([for s in aws_subnet.database : !s.map_public_ip_on_launch])
    error_message = "EKS and DB need separate private subnet tiers in two AZs."
  }
  assert {
    condition     = length(setintersection(toset([for s in aws_subnet.compute : s.cidr_block]), toset([for s in aws_subnet.database : s.cidr_block]))) == 0
    error_message = "The database must not share EKS compute subnets."
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.database_from_eks.from_port == 5432 && aws_vpc_security_group_ingress_rule.database_from_eks.to_port == 5432 && aws_vpc_security_group_ingress_rule.database_from_eks.ip_protocol == "tcp" && aws_vpc_security_group_ingress_rule.database_from_eks.cidr_ipv4 == null
    error_message = "DB ingress must be a security-group reference on PostgreSQL only, not a CIDR-wide rule."
  }
  assert {
    condition     = !aws_db_instance.main.publicly_accessible && aws_db_instance.main.storage_encrypted && aws_db_instance.main.manage_master_user_password && aws_db_instance.main.password == null && aws_db_instance.main.iam_database_authentication_enabled
    error_message = "Keep the database private, encrypted, passwordless for the app, and master credentials out of Terraform."
  }
  assert {
    condition     = aws_db_instance.main.deletion_protection && !aws_db_instance.main.skip_final_snapshot
    error_message = "Default teardown settings must preserve data."
  }
  assert {
    condition     = aws_eks_cluster.main.vpc_config[0].endpoint_private_access && aws_eks_cluster.main.vpc_config[0].public_access_cidrs == toset(var.admin_cidrs)
    error_message = "EKS must have private connectivity and a restricted administrative public endpoint."
  }
  assert {
    condition     = aws_launch_template.nodes.metadata_options[0].http_tokens == "required" && aws_launch_template.nodes.metadata_options[0].http_put_response_hop_limit == 1
    error_message = "Require IMDSv2 and prevent ordinary app Pods falling back to node credentials."
  }
  assert {
    condition     = aws_ecr_repository.app.image_tag_mutability == "IMMUTABLE" && aws_wafv2_web_acl.main[0].scope == "REGIONAL"
    error_message = "Keep immutable images and regional ALB WAF protection."
  }
  assert {
    condition     = jsondecode(aws_iam_role_policy.app_database.policy).Statement[0].Action == "rds-db:connect" && endswith(jsondecode(aws_iam_role_policy.app_database.policy).Statement[0].Resource, "/contoso_app")
    error_message = "Runtime identity must connect only as the restricted app database user."
  }
  assert {
    condition     = jsondecode(aws_iam_role_policy.bootstrap_secret.policy).Statement[0].Action == "secretsmanager:GetSecretValue" && length(local.service_accounts) == 4 && local.service_accounts.app != local.service_accounts.bootstrap
    error_message = "Bootstrap and runtime credentials must have separate identities and purposes."
  }
}
run "private_only_api_and_ha_egress_are_explicit_options" {
  command = plan
  variables {
    environment         = "prod"
    aws_account_id      = "345678901234"
    admin_principal_arn = "arn:aws:iam::345678901234:role/example-admin"
    private_only_api    = true
    nat_per_az          = true
    db_multi_az         = true
    enable_waf          = false
  }
  assert {
    condition     = aws_eks_cluster.main.name == "contoso-prod" && aws_launch_template.nodes.tag_specifications[0].tags["Environment"] == "prod" && aws_launch_template.nodes.tag_specifications[0].tags["Purpose"] == "platform" && !aws_eks_cluster.main.vpc_config[0].endpoint_public_access && aws_eks_cluster.main.vpc_config[0].endpoint_private_access && length(aws_nat_gateway.main) == 2 && aws_db_instance.main.multi_az && length(aws_wafv2_web_acl.main) == 0
    error_message = "Production-oriented options must actually alter the resources."
  }
}
run "reject_open_administrative_api" {
  command = plan
  variables { admin_cidrs = ["0.0.0.0/0"] }
  expect_failures = [var.admin_cidrs]
}
run "reject_sts_session_as_cluster_principal" {
  command = plan
  variables { admin_principal_arn = "arn:aws:sts::123456789012:assumed-role/admin/session" }
  expect_failures = [var.admin_principal_arn]
}
run "reject_vpc_that_makes_alb_subnets_too_small" {
  command = plan
  variables { vpc_cidr = "10.42.0.0/20" }
  expect_failures = [var.vpc_cidr]
}

run "test_environment_has_separate_resource_names" {
  command = plan
  variables {
    environment         = "test"
    aws_account_id      = "234567890123"
    admin_principal_arn = "arn:aws:iam::234567890123:role/example-admin"
  }
  assert {
    condition     = aws_eks_cluster.main.name == "contoso-test" && aws_db_instance.main.identifier == "contoso-test" && aws_iam_role.irsa["app"].name == "contoso-test-app"
    error_message = "Test must use its own cluster, DB and application role names."
  }
}
run "reject_unknown_environment" {
  command = plan
  variables { environment = "staging" }
  expect_failures = [var.environment]
}
run "reject_invalid_account_id" {
  command = plan
  variables { aws_account_id = "not-an-account" }
  expect_failures = [var.aws_account_id]
}
run "reject_admin_from_another_account" {
  command = plan
  variables { admin_principal_arn = "arn:aws:iam::234567890123:role/foreign-admin" }
  expect_failures = [var.admin_principal_arn]
}
