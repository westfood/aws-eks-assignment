variable "environment" {
  description = "dev, test or prod; each uses its own AWS account and state."
  type        = string
  validation {
    condition     = contains(["dev", "test", "prod"], var.environment)
    error_message = "Choose dev, test or prod."
  }
}
variable "aws_account_id" {
  description = "Expected AWS account for this environment. Credentials for another account are rejected."
  type        = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "Supply the 12-digit AWS account ID as a string."
  }
}
variable "aws_region" {
  type    = string
  default = "eu-north-1"
}
variable "state_bucket_name" {
  description = "Bucket holding this environment's infra state. Set by scripts/tf.sh."
  type        = string
}
variable "image_tag" {
  description = "ECR tag pushed by `mise run image`; scripts/tf.sh defaults it to the short Git commit."
  type        = string
  validation {
    condition     = can(regex("^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$", var.image_tag)) && var.image_tag != "latest"
    error_message = "Use the pushed commit tag, not latest."
  }
}
variable "ingress_cidrs" {
  description = "Who may reach the ALB. Null reuses infra's admin_cidrs. 0.0.0.0/0 requires HTTPS."
  type        = list(string)
  default     = null
  validation {
    condition     = var.ingress_cidrs == null ? true : length(var.ingress_cidrs) > 0 && alltrue([for c in var.ingress_cidrs : can(cidrnetmask(c))])
    error_message = "Use a nonempty list of valid IPv4 CIDRs, or null for the restricted default."
  }
}
variable "replicas" {
  type    = number
  default = 2
  validation {
    condition     = var.replicas >= 1 && var.replicas <= 4 && floor(var.replicas) == var.replicas
    error_message = "Use one to four demo replicas."
  }
}
