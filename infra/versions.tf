terraform {
  required_version = ">= 1.14, < 2.0"
  # bucket, key and region are passed by scripts/tf.sh for the selected environment.
  backend "s3" {
    encrypt      = true
    use_lockfile = true
  }
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
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
