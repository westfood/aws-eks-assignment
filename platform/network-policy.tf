resource "kubernetes_network_policy_v1" "default_deny" {
  metadata {
    name      = "default-deny"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
  }
  spec {
    pod_selector {}
    policy_types = ["Ingress", "Egress"]
  }
}
resource "kubernetes_network_policy_v1" "dns" {
  metadata {
    name      = "allow-cluster-dns"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
  }
  spec {
    pod_selector {}
    policy_types = ["Egress"]
    egress {
      to {
        namespace_selector { match_labels = { "kubernetes.io/metadata.name" = "kube-system" } }
        pod_selector { match_labels = { "k8s-app" = "kube-dns" } }
      }
      ports {
        port     = "53"
        protocol = "UDP"
      }
      ports {
        port     = "53"
        protocol = "TCP"
      }
    }
  }
}
resource "kubernetes_network_policy_v1" "database_clients" {
  metadata {
    name      = "allow-app-and-bootstrap-egress"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
  }
  spec {
    pod_selector {
      match_expressions {
        key      = "role"
        operator = "In"
        values   = ["app", "bootstrap"]
      }
    }
    policy_types = ["Egress"]
    egress {
      dynamic "to" {
        for_each = local.infra.database_subnet_cidrs
        content {
          ip_block { cidr = to.value }
        }
      }
      ports {
        port     = "5432"
        protocol = "TCP"
      }
    }
    # EKS Pod Identity agent on the node supplies AWS credentials.
    egress {
      to {
        ip_block { cidr = "169.254.170.23/32" }
      }
      ports {
        port     = "80"
        protocol = "TCP"
      }
    }
    # RDS auth tokens are signed locally; Secrets Manager (bootstrap) uses HTTPS via NAT.
    # Dedicated VPC endpoints + endpoint SGs would narrow this further in production.
    egress {
      to {
        ip_block { cidr = "0.0.0.0/0" }
      }
      ports {
        port     = "443"
        protocol = "TCP"
      }
    }
  }
}
resource "kubernetes_network_policy_v1" "app_ingress" {
  metadata {
    name      = "allow-alb-to-app"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
  }
  spec {
    pod_selector { match_labels = { app = "contoso-app" } }
    policy_types = ["Ingress"]
    ingress {
      dynamic "from" {
        for_each = local.infra.public_subnet_cidrs
        content {
          ip_block { cidr = from.value }
        }
      }
      ports {
        port     = "8080"
        protocol = "TCP"
      }
    }
  }
}
