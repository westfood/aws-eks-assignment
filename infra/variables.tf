variable "name" {
  type    = string
  default = "contoso-demo"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,23}$", var.name))
    error_message = "Use 3–24 lowercase letters, numbers or hyphens, starting with a letter."
  }
}
variable "aws_region" {
  type    = string
  default = "eu-central-1"
}
variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
  validation {
    condition = can(cidrnetmask(var.vpc_cidr)) && try(
      tonumber(split("/", var.vpc_cidr)[1]) >= 16 && tonumber(split("/", var.vpc_cidr)[1]) <= 19,
      false
    )
    error_message = "Use an IPv4 VPC CIDR /16 through /19. The subnet layout adds eight prefix bits; ALB subnets must be /27 or larger."
  }
}
variable "admin_cidrs" {
  description = "Your trusted public IPv4 CIDRs for the Kubernetes API and default demo ingress. Prefer your current /32."
  type        = list(string)
  validation {
    condition = length(var.admin_cidrs) > 0 && alltrue([
      for c in var.admin_cidrs : can(cidrnetmask(c)) && try(tonumber(split("/", c)[1]) >= 24, false)
    ])
    error_message = "Provide at least one trusted IPv4 CIDR /24 or narrower; 0.0.0.0/0 is rejected."
  }
}
variable "admin_principal_arn" {
  description = "Existing IAM role/user ARN allowed to administer this EKS cluster. An STS assumed-role session ARN is not valid."
  type        = string
  validation {
    condition     = can(regex("^arn:aws:iam::[0-9]{12}:(role|user)/.+$", var.admin_principal_arn))
    error_message = "Use an IAM role/user ARN in the commercial AWS partition, not an STS session ARN."
  }
}
variable "private_only_api" {
  description = "Requires an administrator/runner with VPC connectivity. Default keeps public API access restricted to admin_cidrs."
  type        = bool
  default     = false
}
variable "kubernetes_version" {
  description = "Pinned EKS minor version. Confirm availability and standard-support status in your region before deployment."
  type        = string
  default     = "1.36"
}
variable "node_instance_types" {
  type    = list(string)
  default = ["t3.medium"]
}
variable "node_count" {
  type    = number
  default = 2
  validation {
    condition     = var.node_count >= 1 && var.node_count <= 4 && floor(var.node_count) == var.node_count
    error_message = "This small demo supports one to four nodes."
  }
}
variable "nat_per_az" {
  description = "False uses one NAT gateway to reduce demo cost. True creates one per AZ and removes that egress failure dependency."
  type        = bool
  default     = false
}
variable "db_instance_class" {
  description = "IAM database authentication needs memory headroom; a small rather than micro instance is the demo default."
  type        = string
  default     = "db.t4g.small"
}
variable "postgres_engine_version" {
  description = "PostgreSQL version prefix or exact version. The default resolves the latest available minor in major 17; pin the resolved minor before the live apply."
  type        = string
  default     = "17"
  nullable    = false
}
variable "db_multi_az" {
  type    = bool
  default = false
}
variable "db_deletion_protection" {
  type    = bool
  default = true
}
variable "db_skip_final_snapshot" {
  description = "Keep false for data retention. Change to true only for explicitly disposable synthetic demo data."
  type        = bool
  default     = false
}
variable "db_final_snapshot_identifier" {
  description = "Optional unique final snapshot name for cleanup. Null uses <name>-final; choose a fresh name if that snapshot already exists."
  type        = string
  default     = null
  validation {
    condition = var.db_final_snapshot_identifier == null ? true : (
      can(regex("^[a-zA-Z][a-zA-Z0-9-]{0,253}[a-zA-Z0-9]$", var.db_final_snapshot_identifier)) &&
      !strcontains(var.db_final_snapshot_identifier, "--")
    )
    error_message = "Use a 2–255 character snapshot identifier beginning with a letter, without trailing or consecutive hyphens."
  }
}
variable "enable_waf" {
  type    = bool
  default = true
}
