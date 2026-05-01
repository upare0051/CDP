from uuid import uuid4

from app.schemas import TenantCreateRequest, TenantPlanResponse


def build_tenant_plan(payload: TenantCreateRequest) -> TenantPlanResponse:
    tenant_id = f"tnt_{uuid4().hex[:10]}"
    slug = payload.tenant_slug.strip().lower()
    root_domain = f"{slug}.activationos.local"

    return TenantPlanResponse(
        tenant_slug=slug,
        tenant_id=tenant_id,
        website_url=f"https://{root_domain}",
        product_url=f"https://app.{root_domain}",
        admin_url=f"https://admin.{root_domain}",
        terraform_stack="infra/terraform/stacks/tenant-template",
        secret_bindings=[
            "DATABASE_URL",
            "ENCRYPTION_KEY",
            "ADMIN_ANALYTICS_KEY",
        ],
        env_preview={
            "TENANT_ID": tenant_id,
            "TENANT_SLUG": slug,
            "APP_ENV": "production",
            "FRONTEND_URL": f"https://{root_domain}",
            "PUBLIC_DEMO_URL": f"https://app.{root_domain}/dashboard",
            "CUSTOMER_ADMIN_MODE": "tenant_rbac",
        },
    )
