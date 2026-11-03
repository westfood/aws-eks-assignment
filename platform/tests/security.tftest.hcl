mock_provider "aws" {
  mock_data "aws_route53_zone" {
    defaults = { name = "example.com." }
  }
}
mock_provider "helm" {}
mock_provider "kubernetes" {
  mock_resource "kubernetes_ingress_v1" {
    defaults = { status = [{ load_balancer = [{ ingress = [{ hostname = "example.invalid", ip = "" }] }] }] }
  }
}
variables {
  aws_region            = "eu-central-1"
  cluster_name          = "contoso-offline"
  cluster_endpoint      = "https://example.invalid"
  cluster_ca            = "dGVzdC1jYQ=="
  vpc_id                = "vpc-12345678"
  public_subnet_ids     = ["subnet-00000001", "subnet-00000002"]
  public_subnet_cidrs   = ["10.42.0.0/24", "10.42.1.0/24"]
  database_subnet_cidrs = ["10.42.20.0/24", "10.42.21.0/24"]
  database_host         = "example.eu-central-1.rds.amazonaws.com"
  database_name         = "contoso"
  database_user         = "contoso_app"
  bootstrap_secret_arn  = "arn:aws:secretsmanager:eu-central-1:123456789012:secret:example"
  app_role_arn          = "arn:aws:iam::123456789012:role/app"
  bootstrap_role_arn    = "arn:aws:iam::123456789012:role/bootstrap"
  controller_role_arn   = "arn:aws:iam::123456789012:role/controller"
  admin_cidrs           = ["203.0.113.10/32"]
  app_image             = "example.invalid/contoso@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}
run "default_pod_security_and_network_boundaries" {
  command = plan
  assert {
    condition     = kubernetes_namespace_v1.app.metadata[0].labels["pod-security.kubernetes.io/enforce"] == "restricted" && kubernetes_deployment_v1.app.spec[0].template[0].spec[0].security_context[0].run_as_non_root
    error_message = "Run the demo as an unprivileged workload in a restricted namespace."
  }
  assert {
    condition     = kubernetes_deployment_v1.app.spec[0].template[0].spec[0].container[0].security_context[0].read_only_root_filesystem && !kubernetes_service_account_v1.app.automount_service_account_token
    error_message = "Avoid writable roots and unnecessary Kubernetes API tokens."
  }
  assert {
    condition     = kubernetes_service_account_v1.app.metadata[0].annotations["eks.amazonaws.com/role-arn"] != kubernetes_service_account_v1.bootstrap.metadata[0].annotations["eks.amazonaws.com/role-arn"] && local.db_env.DB_AUTH == "iam" && local.db_env.DB_SSLMODE == "verify-full"
    error_message = "Runtime and bootstrap need separate identities and verified database TLS."
  }
  assert {
    condition     = toset(kubernetes_network_policy_v1.default_deny.spec[0].policy_types) == toset(["Ingress", "Egress"]) && kubernetes_service_v1.app.spec[0].type == "ClusterIP"
    error_message = "Default-deny the namespace and expose only the ALB ingress."
  }
  assert {
    condition     = local.annotations["alb.ingress.kubernetes.io/inbound-cidrs"] == "203.0.113.10/32" && local.annotations["alb.ingress.kubernetes.io/target-type"] == "ip"
    error_message = "HTTP-only demo ingress must be source-restricted and use Pod targets."
  }
}
run "https_enables_redirect_and_public_ingress" {
  command = plan
  variables {
    certificate_arn = "arn:aws:acm:eu-central-1:123456789012:certificate/example"
    app_hostname    = "app.example.com"
    ingress_cidrs   = ["0.0.0.0/0"]
  }
  assert {
    condition     = local.annotations["alb.ingress.kubernetes.io/ssl-redirect"] == "443" && local.tls_enabled
    error_message = "Public exposure must redirect HTTP to a trusted HTTPS endpoint."
  }
}
run "reject_public_plaintext_ingress" {
  command = plan
  variables { ingress_cidrs = ["0.0.0.0/0"] }
  expect_failures = [kubernetes_ingress_v1.app]
}
run "reject_mutable_container_tag" {
  command = plan
  variables { app_image = "example.invalid/contoso:latest" }
  expect_failures = [var.app_image]
}
run "reject_zone_apex_cname" {
  command = plan
  variables {
    certificate_arn = "arn:aws:acm:eu-central-1:123456789012:certificate/example"
    app_hostname    = "example.com"
    route53_zone_id = "ZEXAMPLE"
  }
  expect_failures = [aws_route53_record.app]
}
