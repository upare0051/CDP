from pydantic import BaseModel, Field


class TenantCreateRequest(BaseModel):
    tenant_slug: str = Field(..., min_length=3, max_length=64)
    company_name: str = Field(..., min_length=2, max_length=255)
    contact_email: str = Field(..., min_length=5, max_length=255)
    region: str = Field(default="us-central1")
    cloud_project_id: str = Field(..., min_length=3, max_length=128)
    model_default: str = Field(default="meta-llama/llama-3.1-8b-instruct")
    model_fast: str = Field(default="mistralai/mistral-7b-instruct")
    model_smart: str = Field(default="anthropic/claude-3-haiku-20240307")


class TenantPlanResponse(BaseModel):
    tenant_slug: str
    tenant_id: str
    website_url: str
    product_url: str
    admin_url: str
    terraform_stack: str
    secret_bindings: list[str]
    env_preview: dict[str, str]
