mock_provider "aws" {
  mock_data "aws_eks_cluster" {
    defaults = {
      endpoint              = "https://example.invalid"
      certificate_authority = [{ data = "dGVzdC1jYQ==" }]
    }
  }
  mock_data "aws_ecr_image" {
    defaults = { image_digest = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }
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
# Stand-in for infra's state; tests override single outputs where needed.
override_data {
  target = data.terraform_remote_state.infra
  values = {
    outputs = {
      cluster_name          = "contoso-dev"
      vpc_id                = "vpc-12345678"
      public_subnet_ids     = ["subnet-00000001", "subnet-00000002"]
      public_subnet_cidrs   = ["10.42.0.0/24", "10.42.1.0/24"]
      database_subnet_cidrs = ["10.42.20.0/24", "10.42.21.0/24"]
      database_host         = "example.eu-north-1.rds.amazonaws.com"
      database_name         = "contoso"
      database_user         = "contoso_app"
      bootstrap_secret_arn  = "arn:aws:secretsmanager:eu-north-1:123456789012:secret:example"
      waf_acl_arn           = ""
      ecr_repository_url    = "123456789012.dkr.ecr.eu-north-1.amazonaws.com/contoso-dev-app"
      ecr_repository_name   = "contoso-dev-app"
      admin_cidrs           = ["203.0.113.10/32"]
      certificate_arn       = ""
      app_hostname          = ""
      route53_zone_id       = ""
    }
  }
}
variables {
  environment       = "dev"
  aws_account_id    = "123456789012"
  state_bucket_name = "contoso-dev-tfstate-123456789012"
  image_tag         = "abc1234"
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
    condition     = kubernetes_service_account_v1.app.metadata[0].name == "contoso-app" && kubernetes_service_account_v1.bootstrap.metadata[0].name == "contoso-bootstrap" && local.db_env.DB_AUTH == "iam" && local.db_env.DB_SSLMODE == "verify-full"
    error_message = "Service account names must match infra's Pod Identity associations; DB TLS must be verified."
  }
  assert {
    condition     = toset(kubernetes_network_policy_v1.default_deny.spec[0].policy_types) == toset(["Ingress", "Egress"]) && kubernetes_service_v1.app.spec[0].type == "ClusterIP"
    error_message = "Default-deny the namespace and expose only the ALB ingress."
  }
  assert {
    condition     = local.annotations["alb.ingress.kubernetes.io/inbound-cidrs"] == "203.0.113.10/32" && local.annotations["alb.ingress.kubernetes.io/target-type"] == "ip"
    error_message = "HTTP-only demo ingress must be source-restricted and use Pod targets."
  }
  assert {
    condition     = kubernetes_deployment_v1.app.spec[0].template[0].spec[0].container[0].image == "123456789012.dkr.ecr.eu-north-1.amazonaws.com/contoso-dev-app@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    error_message = "Deploy the pushed image from this environment's ECR repository, pinned by digest."
  }
}
run "https_enables_redirect_and_public_ingress" {
  command = plan
  override_data {
    target = data.terraform_remote_state.infra
    values = {
      outputs = {
        cluster_name          = "contoso-dev"
        vpc_id                = "vpc-12345678"
        public_subnet_ids     = ["subnet-00000001", "subnet-00000002"]
        public_subnet_cidrs   = ["10.42.0.0/24", "10.42.1.0/24"]
        database_subnet_cidrs = ["10.42.20.0/24", "10.42.21.0/24"]
        database_host         = "example.eu-north-1.rds.amazonaws.com"
        database_name         = "contoso"
        database_user         = "contoso_app"
        bootstrap_secret_arn  = "arn:aws:secretsmanager:eu-north-1:123456789012:secret:example"
        waf_acl_arn           = "arn:aws:wafv2:eu-north-1:123456789012:regional/webacl/example"
        ecr_repository_url    = "123456789012.dkr.ecr.eu-north-1.amazonaws.com/contoso-dev-app"
        ecr_repository_name   = "contoso-dev-app"
        admin_cidrs           = ["203.0.113.10/32"]
        certificate_arn       = "arn:aws:acm:eu-north-1:123456789012:certificate/example"
        app_hostname          = "app.example.com"
        route53_zone_id       = "ZEXAMPLE"
      }
    }
  }
  variables { ingress_cidrs = ["0.0.0.0/0"] }
  assert {
    condition     = local.annotations["alb.ingress.kubernetes.io/ssl-redirect"] == "443" && local.tls_enabled && local.annotations["alb.ingress.kubernetes.io/wafv2-acl-arn"] != ""
    error_message = "Public exposure must redirect HTTP to HTTPS behind WAF."
  }
}
run "reject_public_plaintext_ingress" {
  command = plan
  variables { ingress_cidrs = ["0.0.0.0/0"] }
  expect_failures = [kubernetes_ingress_v1.app]
}
run "reject_latest_tag" {
  command = plan
  variables { image_tag = "latest" }
  expect_failures = [var.image_tag]
}
run "reject_unknown_environment" {
  command = plan
  variables { environment = "staging" }
  expect_failures = [var.environment]
}
