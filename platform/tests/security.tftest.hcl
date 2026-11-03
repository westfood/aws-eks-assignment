mock_provider "aws" {
  mock_data "aws_eks_cluster" {
    defaults = {
      endpoint              = "https://example.invalid"
      certificate_authority = [{ data = "dGVzdC1jYQ==" }]
    }
  }
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
  environment           = "dev"
  aws_account_id        = "123456789012"
  aws_region            = "eu-central-1"
  cluster_name          = "contoso-dev"
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

run "test_destination_is_environment_qualified" {
  command = plan
  variables {
    environment  = "test"
    cluster_name = "contoso-test"
  }
  assert {
    condition     = data.aws_eks_cluster.target.name == "contoso-test" && kubernetes_namespace_v1.app.metadata[0].labels["environment"] == "test"
    error_message = "The platform must resolve its cluster and label workloads for the selected test target."
  }
}
run "prod_destination_is_environment_qualified" {
  command = plan
  variables {
    environment  = "prod"
    cluster_name = "contoso-prod"
  }
  assert {
    condition     = data.aws_eks_cluster.target.name == "contoso-prod"
    error_message = "The platform must resolve the selected production cluster."
  }
}
run "reject_unknown_environment" {
  command = plan
  variables { environment = "staging" }
  expect_failures = [var.environment]
}
run "reject_invalid_account_id" {
  command = plan
  variables { aws_account_id = "not-an-account" }
  expect_failures = [var.aws_account_id]
}
run "reject_cluster_from_another_environment" {
  command = plan
  variables { cluster_name = "contoso-prod" }
  expect_failures = [var.cluster_name]
}
run "reject_mixed_cluster_metadata" {
  command = plan
  variables { cluster_endpoint = "https://foreign.invalid" }
  expect_failures = [data.aws_eks_cluster.target]
}
run "reject_runtime_role_from_another_account" {
  command = plan
  variables { app_role_arn = "arn:aws:iam::234567890123:role/foreign-runtime" }
  expect_failures = [var.app_role_arn]
}
run "reject_bootstrap_secret_from_another_account" {
  command = plan
  variables { bootstrap_secret_arn = "arn:aws:secretsmanager:eu-central-1:234567890123:secret:foreign" }
  expect_failures = [var.bootstrap_secret_arn]
}
run "reject_certificate_from_another_region" {
  command = plan
  variables {
    app_hostname    = "app.example.com"
    certificate_arn = "arn:aws:acm:us-east-1:123456789012:certificate/foreign"
  }
  expect_failures = [var.certificate_arn]
}
