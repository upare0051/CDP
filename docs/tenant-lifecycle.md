# Tenant Lifecycle (Target)

1. Create tenant in control-plane
2. Provision infra via Terraform tenant-template
3. Bind secrets + config
4. Deploy product frontend/backend/admin
5. Run migrations + health checks
6. Send admin invite URL
