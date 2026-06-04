---
name: shotgrid-crud
description: >-
  ShotGrid CRUD skill — create, read, update, and delete ShotGrid entities.
  Use when an AI agent needs to manage ShotGrid data: find entities, create
  new records, update fields, or delete/retire entities. Not for batch
  operations or schema queries.
license: MIT
compatibility: "Python 3.8+; dcc-mcp-core 0.17+"
allowed-tools: Bash Read Write Edit
metadata:
  dcc-mcp:
    dcc: shotgrid
    version: "0.1.0"
    layer: domain
    stage: scene
    tags: ["crud", "entity", "create", "update", "delete", "shotgrid"]
    search-hint: "find shotgrid entity, create shot, update task, delete asset, find one"
    tools: tools.yaml
---

# ShotGrid CRUD

Core entity management for ShotGrid. Provides the standard CRUD surface
plus single-entity lookup. All destructive operations log the change;
`delete_entity` retires entities rather than permanently removing them.

All tools accept optional `project`, `project_id`, and `project_scoped`
inputs. When omitted, the server uses `SHOTGRID_PROJECT` or
`SHOTGRID_PROJECT_ID` if configured. Reads add a project filter, creates
inject `data.project` when missing, and updates/deletes enforce the configured
project permission policy.

## Tools

| Tool | Intent |
|------|--------|
| `find_entities` | Search entities with filters, pagination, and field selection |
| `find_one_entity` | Find a single entity by filters, return None if not found |
| `create_entity` | Create a new entity with field values |
| `update_entity` | Update fields on an existing entity by ID |
| `delete_entity` | Retire an entity (soft-delete) |

## After Success

- `find_entities` and `find_one_entity` return the entity dict(s).
- `create_entity` returns the new entity with its generated ID.
- `update_entity` returns the updated fields.
- `delete_entity` returns True.

## After Failure

- Check `shotgrid-discovery__check_connection` to verify credentials.
- Verify entity type exists via `shotgrid-discovery__list_entity_types`.
- Check field names via `shotgrid-schema__get_field_schema`.
- If permission is denied, inspect `SHOTGRID_PERMISSION_LEVEL` and
  `SHOTGRID_PROJECT_PERMISSIONS`; delete/retire requires `admin`.
