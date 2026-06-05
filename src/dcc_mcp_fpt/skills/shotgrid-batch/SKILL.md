---
name: shotgrid-batch
description: >-
  ShotGrid batch operations skill — create, update, or delete multiple entities
  in a single API call. Use when an AI agent needs to perform the same operation
  on many entities efficiently. Not for single-entity CRUD — use shotgrid-crud.
license: MIT
compatibility: "Python 3.8+; dcc-mcp-core >=0.18.2,<1.0.0"
allowed-tools: Bash Read Write Edit
metadata:
  dcc-mcp:
    dcc: shotgrid
    version: "0.1.0"
    layer: domain
    stage: pipeline
    tags: ["batch", "bulk", "pipeline", "shotgrid"]
    search-hint: "batch create entities, bulk update, batch delete, multiple entities"
    tools: tools.yaml
---

# ShotGrid Batch

Run multiple create, update, and delete operations in a single ShotGrid API
call. Ideal for pipeline automation and bulk data tasks.

The tool accepts optional `project`, `project_id`, and `project_scoped`
inputs. Creates inherit the default project when `data.project` is missing;
updates and deletes validate each request against the configured project
permission policy before the batch is sent.

## Tools

| Tool | Intent |
|------|--------|
| `batch_operations` | Execute a list of create/update/delete requests atomically |

## After Success

- Returns results array matching request order (one result per request).
- Failed items appear in results with error details.

## After Failure

- Check individual request items for errors.
- Verify credentials via `shotgrid-discovery__check_connection`.
- Delete requests require `admin` permission for the target project.
