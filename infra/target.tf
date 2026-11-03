variable "environment" {
  description = "Explicit deployment target; each environment uses its own AWS account and state."
  type        = string
  nullable    = false
  validation {
    condition     = contains(["dev", "test", "prod"], var.environment)
    error_message = "Choose dev, test or prod."
  }
}
variable "aws_account_id" {
  description = "Expected AWS account for this target. Credentials for another account are rejected."
  type        = string
  nullable    = false
  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "Supply the target's 12-digit AWS account ID as a string."
  }
}

locals {
  name = "${var.name}-${var.environment}"
}
