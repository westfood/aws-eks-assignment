variable "tls_domain_name" {
  description = "Optional owned subdomain, e.g. app.example.com. Leave empty for the restricted HTTP-only lab endpoint."
  type        = string
  default     = ""
}
variable "tls_zone_id" {
  description = "Optional Route53 PUBLIC hosted zone ID for tls_domain_name. Domain delegation must already work."
  type        = string
  default     = ""
  validation {
    condition     = (var.tls_zone_id == "") == (var.tls_domain_name == "")
    error_message = "Set both tls_domain_name and tls_zone_id, or leave both empty."
  }
}
resource "aws_acm_certificate" "app" {
  count             = var.tls_domain_name == "" ? 0 : 1
  domain_name       = var.tls_domain_name
  validation_method = "DNS"
  lifecycle { create_before_destroy = true }
}
resource "aws_route53_record" "certificate_validation" {
  count           = var.tls_domain_name == "" ? 0 : 1
  zone_id         = var.tls_zone_id
  name            = tolist(aws_acm_certificate.app[0].domain_validation_options)[0].resource_record_name
  type            = tolist(aws_acm_certificate.app[0].domain_validation_options)[0].resource_record_type
  records         = [tolist(aws_acm_certificate.app[0].domain_validation_options)[0].resource_record_value]
  ttl             = 60
  allow_overwrite = false
}
resource "aws_acm_certificate_validation" "app" {
  count                   = var.tls_domain_name == "" ? 0 : 1
  certificate_arn         = aws_acm_certificate.app[0].arn
  validation_record_fqdns = [aws_route53_record.certificate_validation[0].fqdn]
}
output "certificate_arn" { value = var.tls_domain_name == "" ? "" : aws_acm_certificate_validation.app[0].certificate_arn }
output "app_hostname" { value = var.tls_domain_name }
output "route53_zone_id" { value = var.tls_zone_id }
