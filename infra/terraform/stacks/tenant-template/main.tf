terraform {
  required_version = ">= 1.5.0"
}

locals {
  website_host = "${var.tenant_slug}.${var.domain_root}"
  app_host     = "app.${var.tenant_slug}.${var.domain_root}"
  admin_host   = "admin.${var.tenant_slug}.${var.domain_root}"
}

# Phase 1 note:
# This stack is intentionally scaffold-only.
# Module wiring will be added incrementally in Phase 2 to avoid impacting live runtime.
#
# Example future modules:
# module "network" {}
# module "database" {}
# module "backend_service" {}
# module "frontend_service" {}
# module "auth" {}
# module "secrets" {}
# module "monitoring" {}
