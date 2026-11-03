terraform {
  required_version = ">= 1.14, < 2.0"
  backend "s3" {}
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
    tls = { source = "hashicorp/tls", version = "~> 4.0" }
  }
}

provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.aws_account_id]
  default_tags {
    tags = {
      Project = local.name, Environment = var.environment, ManagedBy = "terraform"
      Purpose = var.environment == "dev" ? "interview" : "platform"
    }
  }
}
