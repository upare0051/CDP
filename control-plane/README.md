# Control Plane (Scaffold)

Internal system for tenant lifecycle automation:

- create tenant
- provision infra via Terraform
- bind secrets/config
- deploy frontend/backend/admin
- health checks + rollback hooks
