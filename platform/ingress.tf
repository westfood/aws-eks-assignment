locals {
  ingress_cidrs = var.ingress_cidrs == null ? var.admin_cidrs : var.ingress_cidrs
  tls_enabled   = var.certificate_arn != ""
  annotations = merge({
    "alb.ingress.kubernetes.io/scheme"                       = "internet-facing"
    "alb.ingress.kubernetes.io/target-type"                  = "ip"
    "alb.ingress.kubernetes.io/subnets"                      = join(",", var.public_subnet_ids)
    "alb.ingress.kubernetes.io/inbound-cidrs"                = join(",", local.ingress_cidrs)
    "alb.ingress.kubernetes.io/healthcheck-path"             = "/readyz"
    "alb.ingress.kubernetes.io/healthcheck-timeout-seconds"  = "20"
    "alb.ingress.kubernetes.io/healthcheck-interval-seconds" = "30"
    "alb.ingress.kubernetes.io/success-codes"                = "200"
    "alb.ingress.kubernetes.io/listen-ports"                 = local.tls_enabled ? "[{\"HTTP\":80},{\"HTTPS\":443}]" : "[{\"HTTP\":80}]"
    "alb.ingress.kubernetes.io/load-balancer-attributes"     = "routing.http.drop_invalid_header_fields.enabled=true"
    "alb.ingress.kubernetes.io/tags"                         = "Project=${var.cluster_name},Environment=${var.environment},ManagedBy=aws-load-balancer-controller"
    }, local.tls_enabled ? {
    "alb.ingress.kubernetes.io/certificate-arn" = var.certificate_arn
    "alb.ingress.kubernetes.io/ssl-redirect"    = "443"
    "alb.ingress.kubernetes.io/ssl-policy"      = "ELBSecurityPolicy-TLS13-1-2-2021-06"
    } : {}, var.waf_acl_arn != "" ? {
    "alb.ingress.kubernetes.io/wafv2-acl-arn" = var.waf_acl_arn
  } : {})
}
resource "kubernetes_ingress_v1" "app" {
  metadata {
    name        = "contoso-app"
    namespace   = kubernetes_namespace_v1.app.metadata[0].name
    annotations = local.annotations
  }
  wait_for_load_balancer = true
  spec {
    ingress_class_name = "alb"
    rule {
      host = var.app_hostname == "" ? null : var.app_hostname
      http {
        path {
          path      = "/"
          path_type = "Prefix"
          backend {
            service {
              name = kubernetes_service_v1.app.metadata[0].name
              port { number = 8080 }
            }
          }
        }
      }
    }
  }
  lifecycle {
    precondition {
      condition     = local.tls_enabled || !contains(local.ingress_cidrs, "0.0.0.0/0")
      error_message = "Do not expose the HTTP-only demo to the entire internet. Configure a trusted HTTPS hostname/certificate first."
    }
  }
  depends_on = [helm_release.controller, kubernetes_deployment_v1.app]
}
data "aws_route53_zone" "app" {
  count   = var.route53_zone_id == "" ? 0 : 1
  zone_id = var.route53_zone_id
}
resource "aws_route53_record" "app" {
  count   = var.route53_zone_id == "" ? 0 : 1
  zone_id = var.route53_zone_id
  name    = var.app_hostname
  type    = "CNAME"
  ttl     = 60
  records = [kubernetes_ingress_v1.app.status[0].load_balancer[0].ingress[0].hostname]
  lifecycle {
    precondition {
      condition     = lower(trimsuffix(var.app_hostname, ".")) != lower(trimsuffix(data.aws_route53_zone.app[0].name, "."))
      error_message = "Use a subdomain such as demo.example.com. This CNAME record cannot use the hosted-zone apex."
    }
  }
}
output "alb_hostname" { value = kubernetes_ingress_v1.app.status[0].load_balancer[0].ingress[0].hostname }
output "application_url" {
  value = local.tls_enabled ? "https://${var.app_hostname}" : "http://${kubernetes_ingress_v1.app.status[0].load_balancer[0].ingress[0].hostname}"
}
