# Migration Plan (Non-Breaking)

## Phase 0 (Done)
- Backup snapshot created before structural changes
- New scaffold directories added without moving live code

## Phase 1
- Introduce shared config schema
- Start extracting website-specific code into `apps/website/*`

## Phase 2
- Extract product code into `apps/product/*`
- Add control-plane deploy API and Terraform tenant-template

## Phase 3
- Run parallel staging deploys
- Cut over production traffic in controlled steps
