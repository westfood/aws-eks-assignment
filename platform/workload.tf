locals {
  namespace = "contoso"
  db_env = {
    DB_AUTH                    = "iam"
    DB_HOST                    = var.database_host
    DB_PORT                    = "5432"
    DB_NAME                    = var.database_name
    DB_USER                    = var.database_user
    AWS_REGION                 = var.aws_region
    AWS_DEFAULT_REGION         = var.aws_region
    AWS_EC2_METADATA_DISABLED  = "true"
    AWS_STS_REGIONAL_ENDPOINTS = "regional"
    DB_SSLMODE                 = "verify-full"
    RDS_CA_BUNDLE              = "/app/certs/global-bundle.pem"
  }
}
resource "kubernetes_namespace_v1" "app" {
  metadata {
    name = local.namespace
    labels = {
      "environment"                        = var.environment
      "pod-security.kubernetes.io/enforce" = "restricted"
      "pod-security.kubernetes.io/audit"   = "restricted"
      "pod-security.kubernetes.io/warn"    = "restricted"
    }
  }
}
resource "kubernetes_service_account_v1" "app" {
  metadata {
    name      = "contoso-app"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
    annotations = {
      "eks.amazonaws.com/role-arn"               = var.app_role_arn
      "eks.amazonaws.com/sts-regional-endpoints" = "true"
    }
  }
  automount_service_account_token = false
}
resource "kubernetes_service_account_v1" "bootstrap" {
  metadata {
    name      = "contoso-bootstrap"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
    annotations = {
      "eks.amazonaws.com/role-arn"               = var.bootstrap_role_arn
      "eks.amazonaws.com/sts-regional-endpoints" = "true"
    }
  }
  automount_service_account_token = false
}
resource "kubernetes_job_v1" "bootstrap" {
  metadata {
    name      = "database-bootstrap"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
  }
  wait_for_completion = true
  spec {
    backoff_limit           = 1
    active_deadline_seconds = 300
    template {
      metadata { labels = { role = "bootstrap" } }
      spec {
        service_account_name            = kubernetes_service_account_v1.bootstrap.metadata[0].name
        automount_service_account_token = false
        restart_policy                  = "Never"
        security_context {
          run_as_non_root = true
          run_as_user     = 10001
          run_as_group    = 10001
          fs_group        = 10001
          seccomp_profile { type = "RuntimeDefault" }
        }
        container {
          name    = "bootstrap"
          image   = var.app_image
          command = ["python", "-m", "demo.bootstrap"]
          dynamic "env" {
            for_each = merge(local.db_env, { BOOTSTRAP_SECRET_ARN = var.bootstrap_secret_arn, BOOTSTRAP_APP_USER = var.database_user })
            content {
              name  = env.key
              value = env.value
            }
          }
          resources {
            requests = { cpu = "100m", memory = "128Mi" }
            limits   = { cpu = "500m", memory = "256Mi" }
          }
          security_context {
            allow_privilege_escalation = false
            read_only_root_filesystem  = true
            capabilities { drop = ["ALL"] }
          }
          volume_mount {
            name       = "tmp"
            mount_path = "/tmp"
          }
        }
        volume {
          name = "tmp"
          empty_dir { size_limit = "64Mi" }
        }
      }
    }
  }
  timeouts {
    create = "6m"
    update = "6m"
  }
  depends_on = [kubernetes_network_policy_v1.default_deny, kubernetes_network_policy_v1.dns, kubernetes_network_policy_v1.database_clients]
}
resource "kubernetes_deployment_v1" "app" {
  metadata {
    name      = "contoso-app"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
  }
  spec {
    replicas = var.replicas
    selector { match_labels = { app = "contoso-app" } }
    strategy {
      type = "RollingUpdate"
      rolling_update {
        max_surge       = "1"
        max_unavailable = "0"
      }
    }
    template {
      metadata { labels = { app = "contoso-app", role = "app" } }
      spec {
        service_account_name            = kubernetes_service_account_v1.app.metadata[0].name
        automount_service_account_token = false
        security_context {
          run_as_non_root = true
          run_as_user     = 10001
          run_as_group    = 10001
          fs_group        = 10001
          seccomp_profile { type = "RuntimeDefault" }
        }
        container {
          name  = "app"
          image = var.app_image
          port {
            name           = "http"
            container_port = 8080
          }
          dynamic "env" {
            for_each = local.db_env
            content {
              name  = env.key
              value = env.value
            }
          }
          resources {
            requests = { cpu = "100m", memory = "128Mi" }
            limits   = { memory = "256Mi" }
          }
          security_context {
            allow_privilege_escalation = false
            read_only_root_filesystem  = true
            capabilities { drop = ["ALL"] }
          }
          startup_probe {
            http_get {
              path = "/healthz"
              port = "http"
            }
            period_seconds    = 5
            failure_threshold = 24
          }
          liveness_probe {
            http_get {
              path = "/healthz"
              port = "http"
            }
            period_seconds = 15
          }
          readiness_probe {
            http_get {
              path = "/readyz"
              port = "http"
            }
            period_seconds    = 20
            timeout_seconds   = 20
            failure_threshold = 3
          }
          volume_mount {
            name       = "tmp"
            mount_path = "/tmp"
          }
        }
        volume {
          name = "tmp"
          empty_dir { size_limit = "64Mi" }
        }
      }
    }
  }
  depends_on = [kubernetes_job_v1.bootstrap, kubernetes_network_policy_v1.app_ingress]
}
resource "kubernetes_service_v1" "app" {
  metadata {
    name      = "contoso-app"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
  }
  spec {
    type     = "ClusterIP"
    selector = { app = "contoso-app" }
    port {
      name        = "http"
      port        = 8080
      target_port = "http"
    }
  }
}
