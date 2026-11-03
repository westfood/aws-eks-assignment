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

run "default_does_not_take_registry_ownership" {
  command = plan

  assert {
    condition     = length(aws_ecr_registry_scanning_configuration.app) == 0 && !output.ecr_registry_scanning_managed
    error_message = "Existing account-wide registry settings must remain unmanaged unless ownership is explicitly enabled."
  }
  assert {
    condition     = output.ecr_scan_type == "BASIC" && output.ecr_scan_frequency == "SCAN_ON_PUSH" && aws_ecr_repository.app.image_scanning_configuration[0].scan_on_push
    error_message = "The default policy must retain repository-level BASIC scanning on push."
  }
}

run "basic_registry_scans_app_prefix_on_push" {
  command = plan
  variables { manage_ecr_registry_scanning = true }

  assert {
    condition     = length(aws_ecr_registry_scanning_configuration.app) == 1 && aws_ecr_registry_scanning_configuration.app[0].scan_type == "BASIC" && output.ecr_registry_scanning_managed
    error_message = "Explicit ownership must manage a single BASIC registry configuration."
  }
  assert {
    condition     = one(aws_ecr_registry_scanning_configuration.app[0].rule).scan_frequency == "SCAN_ON_PUSH" && length(aws_ecr_registry_scanning_configuration.app[0].rule) == 1
    error_message = "BASIC registry policy must scan matching repositories on push."
  }
  assert {
    condition     = length(aws_ecr_repository.app.image_scanning_configuration) == 0
    error_message = "Managed BASIC scanning must use registry rules without the legacy repository setting."
  }
  assert {
    condition     = one(one(aws_ecr_registry_scanning_configuration.app[0].rule).repository_filter).filter == "contoso-dev-app*" && one(one(aws_ecr_registry_scanning_configuration.app[0].rule).repository_filter).filter_type == "WILDCARD" && output.ecr_repository_name == "contoso-dev-app"
    error_message = "Scope the rule to the explicit app repository prefix, including the wildcard."
  }
}

run "enhanced_registry_uses_inspector_continuous_scanning" {
  command = plan
  variables {
    environment                  = "prod"
    aws_account_id               = "345678901234"
    admin_principal_arn          = "arn:aws:iam::345678901234:role/example-admin"
    manage_ecr_registry_scanning = true
    ecr_scan_type                = "ENHANCED"
  }

  assert {
    condition     = aws_ecr_registry_scanning_configuration.app[0].scan_type == "ENHANCED" && one(aws_ecr_registry_scanning_configuration.app[0].rule).scan_frequency == "CONTINUOUS_SCAN" && output.ecr_scan_type == "ENHANCED" && output.ecr_scan_frequency == "CONTINUOUS_SCAN"
    error_message = "ENHANCED must request Amazon Inspector continuous scanning."
  }
  assert {
    condition     = length(aws_ecr_repository.app.image_scanning_configuration) == 0
    error_message = "ENHANCED scanning must not configure the legacy BASIC repository setting."
  }
  assert {
    condition     = one(one(aws_ecr_registry_scanning_configuration.app[0].rule).repository_filter).filter == "contoso-prod-app*" && one(one(aws_ecr_registry_scanning_configuration.app[0].rule).repository_filter).filter_type == "WILDCARD"
    error_message = "Production registry rules must use the production app prefix."
  }
}

run "external_platform_can_own_enhanced_registry" {
  command = plan
  variables {
    manage_ecr_registry_scanning = false
    ecr_scan_type                = "ENHANCED"
  }

  assert {
    condition     = length(aws_ecr_registry_scanning_configuration.app) == 0 && !output.ecr_registry_scanning_managed && output.ecr_scan_type == "ENHANCED" && length(aws_ecr_repository.app.image_scanning_configuration) == 0
    error_message = "An externally managed enhanced policy must not create the account-wide singleton in this state."
  }
}

run "reject_invalid_scan_type" {
  command = plan
  variables { ecr_scan_type = "NONE" }
  expect_failures = [var.ecr_scan_type]
}
