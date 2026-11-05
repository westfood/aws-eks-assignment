resource "kubernetes_service_account_v1" "controller" {
  metadata {
    name      = "aws-load-balancer-controller"
    namespace = "kube-system"
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
    clusterName                 = local.infra.cluster_name
    region                      = var.aws_region
    vpcId                       = local.infra.vpc_id
    replicaCount                = 1
    serviceAccount              = { create = false, name = kubernetes_service_account_v1.controller.metadata[0].name }
    enableServiceMutatorWebhook = false
    # Shield is not available in AWS-managed projects and WAF Classic is retired; WAFv2 stays on.
    enableShield = false
    enableWaf    = false
    enableWafv2  = true
    resources = {
      requests = { cpu = "100m", memory = "128Mi" }
      limits   = { memory = "256Mi" }
    }
  })]
}
