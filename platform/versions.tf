terraform {
  required_version = ">= 1.14, < 2.0"
  backend "s3" {}
  required_providers {
    kubernetes = { source = "hashicorp/kubernetes", version = "~> 2.38" }
    helm       = { source = "hashicorp/helm", version = "~> 3.0" }
    aws        = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}
provider "aws" { region = var.aws_region }
provider "kubernetes" {
  host                   = var.cluster_endpoint
  cluster_ca_certificate = base64decode(var.cluster_ca)
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", var.cluster_name, "--region", var.aws_region]
  }
}
provider "helm" {
  kubernetes = {
    host                   = var.cluster_endpoint
    cluster_ca_certificate = base64decode(var.cluster_ca)
    exec = {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", var.cluster_name, "--region", var.aws_region]
    }
  }
}
