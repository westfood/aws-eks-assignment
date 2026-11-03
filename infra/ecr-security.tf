variable "manage_ecr_registry_scanning" {
  description = "Own the account/Region-wide ECR scanning configuration. Enable only in a dedicated account or when this state owns the complete registry policy; other repositories are also affected. Destroy resets the registry to BASIC without rules."
  type        = bool
  default     = false
  nullable    = false
}

variable "ecr_scan_type" {
  description = "Requested ECR policy: BASIC scans on push; ENHANCED uses Amazon Inspector continuous scanning and incurs Inspector charges. With registry management disabled, the account owner must configure the requested mode."
  type        = string
  default     = "BASIC"
  nullable    = false

  validation {
    condition     = contains(["BASIC", "ENHANCED"], var.ecr_scan_type)
    error_message = "Choose BASIC or ENHANCED for ecr_scan_type."
  }
}

locals {
  ecr_scan_frequency = var.ecr_scan_type == "ENHANCED" ? "CONTINUOUS_SCAN" : "SCAN_ON_PUSH"
}

# This is one singleton per AWS account and Region, not a repository resource.
# Under ENHANCED, repositories outside this prefix have scanning turned off;
# under BASIC they retain manual scanning. Import/merge an existing registry
# policy before enabling ownership in an account that already has repositories.
resource "aws_ecr_registry_scanning_configuration" "app" {
  count = var.manage_ecr_registry_scanning ? 1 : 0

  scan_type = var.ecr_scan_type

  rule {
    scan_frequency = local.ecr_scan_frequency

    repository_filter {
      # ECR treats a literal without '*' as a substring, not an exact match.
      # This intentionally covers the app repository and its prefix variants.
      filter      = "${aws_ecr_repository.app.name}*"
      filter_type = "WILDCARD"
    }
  }
}
