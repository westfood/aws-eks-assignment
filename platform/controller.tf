resource "kubernetes_service_account_v1" "controller" {
  metadata {
    name      = "aws-load-balancer-controller"
    namespace = "kube-system"
    annotations = {
      "eks.amazonaws.com/role-arn"               = var.controller_role_arn
      "eks.amazonaws.com/sts-regional-endpoints" = "true"
    }
  }
}
resource "helm_release" "controller" {
  name       = "aws-load-balancer-controller"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  version    = "1.14.1"
  namespace  = "kube-system"
  atomic     = true
  wait       = true
  timeout    = 600
  values = [yamlencode({
    clusterName                 = var.cluster_name
    region                      = var.aws_region
    vpcId                       = var.vpc_id
    replicaCount                = 1
    serviceAccount              = { create = false, name = kubernetes_service_account_v1.controller.metadata[0].name }
    enableServiceMutatorWebhook = false
    resources = {
      requests = { cpu = "100m", memory = "128Mi" }
      limits   = { memory = "256Mi" }
    }
  })]
}
