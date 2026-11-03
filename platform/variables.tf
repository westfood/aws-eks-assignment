variable "aws_region" { type = string }
variable "cluster_name" {
  type = string
  validation {
    condition = contains(["dev", "test", "prod"], var.environment) ? (
      endswith(var.cluster_name, "-${var.environment}")
    ) : true
    error_message = "The EKS cluster name must end in the selected environment suffix, such as contoso-dev."
  }
}
variable "cluster_endpoint" { type = string }
variable "cluster_ca" { type = string }
variable "vpc_id" { type = string }
variable "public_subnet_ids" { type = list(string) }
variable "public_subnet_cidrs" { type = list(string) }
variable "database_subnet_cidrs" { type = list(string) }
variable "database_host" { type = string }
variable "database_name" { type = string }
variable "database_user" { type = string }
variable "bootstrap_secret_arn" {
  type = string
  validation {
    condition = can(regex("^[0-9]{12}$", var.aws_account_id)) ? (
      startswith(var.bootstrap_secret_arn, "arn:aws:secretsmanager:${var.aws_region}:${var.aws_account_id}:secret:")
    ) : true
    error_message = "bootstrap_secret_arn must belong to the selected AWS account and Region."
  }
}
variable "app_role_arn" {
  type = string
  validation {
    condition = can(regex("^[0-9]{12}$", var.aws_account_id)) ? (
      startswith(var.app_role_arn, "arn:aws:iam::${var.aws_account_id}:role/")
    ) : true
    error_message = "app_role_arn must belong to the selected AWS account."
  }
}
variable "bootstrap_role_arn" {
  type = string
  validation {
    condition = can(regex("^[0-9]{12}$", var.aws_account_id)) ? (
      startswith(var.bootstrap_role_arn, "arn:aws:iam::${var.aws_account_id}:role/")
    ) : true
    error_message = "bootstrap_role_arn must belong to the selected AWS account."
  }
}
variable "controller_role_arn" {
  type = string
  validation {
    condition = can(regex("^[0-9]{12}$", var.aws_account_id)) ? (
      startswith(var.controller_role_arn, "arn:aws:iam::${var.aws_account_id}:role/")
    ) : true
    error_message = "controller_role_arn must belong to the selected AWS account."
  }
}
variable "waf_acl_arn" {
  type    = string
  default = ""
  validation {
    condition = var.waf_acl_arn == "" || !can(regex("^[0-9]{12}$", var.aws_account_id)) ? true : (
      startswith(var.waf_acl_arn, "arn:aws:wafv2:${var.aws_region}:${var.aws_account_id}:regional/webacl/")
    )
    error_message = "waf_acl_arn must belong to the selected AWS account and Region."
  }
}
variable "admin_cidrs" { type = list(string) }
variable "app_image" {
  description = "Push the app to ECR and supply its immutable repository@sha256 digest."
  type        = string
  validation {
    condition     = can(regex("^[^[:space:]]+@sha256:[a-f0-9]{64}$", var.app_image))
    error_message = "Supply an image pinned by sha256 digest, not a mutable tag."
  }
}
variable "certificate_arn" {
  type    = string
  default = ""
  validation {
    condition = var.certificate_arn == "" || !can(regex("^[0-9]{12}$", var.aws_account_id)) ? true : (
      startswith(var.certificate_arn, "arn:aws:acm:${var.aws_region}:${var.aws_account_id}:certificate/")
    )
    error_message = "certificate_arn must belong to the selected AWS account and Region."
  }
}
variable "app_hostname" {
  type    = string
  default = ""
  validation {
    condition     = (var.app_hostname == "") == (var.certificate_arn == "")
    error_message = "A trusted HTTPS endpoint needs both an owned hostname and a regional ACM certificate ARN."
  }
}
variable "route53_zone_id" {
  type    = string
  default = ""
  validation {
    condition     = var.route53_zone_id == "" || var.app_hostname != ""
    error_message = "A Route53 record needs the application hostname and certificate inputs."
  }
}
variable "ingress_cidrs" {
  description = "Null uses the same trusted sources as the Kubernetes API. Public 0.0.0.0/0 requires HTTPS."
  type        = list(string)
  default     = null
  nullable    = true
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
