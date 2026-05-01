from fastapi import FastAPI

from app.schemas import TenantCreateRequest, TenantPlanResponse
from app.services.tenant_plan import build_tenant_plan

app = FastAPI(
    title="Alo ActivationOS Control Plane API",
    version="0.1.0",
    description="Internal control-plane API for tenant planning and one-click deployment orchestration.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/tenants/plan", response_model=TenantPlanResponse)
def plan_tenant(payload: TenantCreateRequest) -> TenantPlanResponse:
    """
    Creates a deterministic deployment plan for a new tenant.
    This endpoint is planning-only for now (non-mutating scaffold).
    """
    return build_tenant_plan(payload)
