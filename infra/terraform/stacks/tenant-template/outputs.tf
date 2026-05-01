output "website_url" {
  value = "https://${var.tenant_slug}.${var.domain_root}"
}

output "product_url" {
  value = "https://app.${var.tenant_slug}.${var.domain_root}"
}

output "admin_url" {
  value = "https://admin.${var.tenant_slug}.${var.domain_root}"
}

output "ai_provider" {
  value = var.ai_provider
}
