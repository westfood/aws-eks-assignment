# Everything this root needs from infra (cluster, roles, subnets, DB) comes from infra's state.
data "terraform_remote_state" "infra" {
  backend = "s3"
  config = {
    bucket = var.state_bucket_name
    key    = "infra.tfstate"
    region = var.aws_region
  }
}
# Lists the pushed images. Unlike aws_ecr_image it doesn't fail on a missing tag, so destroy works without one.
data "aws_ecr_images" "app" {
  repository_name = local.infra.ecr_repository_name
}
locals {
  infra = data.terraform_remote_state.infra.outputs
  # Pods are pinned to the digest. Null if the tag was never pushed; the Deployment's precondition then fails the plan.
  image_digest = one([for i in data.aws_ecr_images.app.image_ids : i.image_digest if i.image_tag == var.image_tag])
  app_image    = local.image_digest == null ? null : "${local.infra.ecr_repository_url}@${local.image_digest}"
}
data "aws_eks_cluster" "target" {
  name = local.infra.cluster_name
}
