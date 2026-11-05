# Everything this root needs from infra (cluster, roles, subnets, DB) comes from infra's state.
data "terraform_remote_state" "infra" {
  backend = "s3"
  config = {
    bucket = var.state_bucket_name
    key    = "infra.tfstate"
    region = var.aws_region
  }
}
# Fails the plan if the tag was never pushed, and pins the Pods to the image digest.
data "aws_ecr_image" "app" {
  repository_name = local.infra.ecr_repository_name
  image_tag       = var.image_tag
}
locals {
  infra     = data.terraform_remote_state.infra.outputs
  app_image = "${local.infra.ecr_repository_url}@${data.aws_ecr_image.app.image_digest}"
}
data "aws_eks_cluster" "target" {
  name = local.infra.cluster_name
}
