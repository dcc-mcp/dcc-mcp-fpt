---
name: shotgrid-schema
description: >-
  ShotGrid schema skill — inspect entity field definitions, data types,
  and valid values. Use when an AI agent needs to understand what fields
  exist on an entity, their types, constraints, and valid values before
  creating or updating data. Not for entity CRUD — use shotgrid-crud.
license: MIT
compatibility: "Python 3.8+; dcc-mcp-core >=0.18.2,<1.0.0"
allowed-tools: Bash Read Write Edit
metadata:
  dcc-mcp:
    dcc: shotgrid
    version: "0.1.0"
    layer: domain
    stage: bootstrap
    tags: ["schema", "fields", "metadata", "introspection", "shotgrid"]
    search-hint: "get field schema, entity fields, field types, valid values, data model"
    tools: tools.yaml
---

# ShotGrid Schema

Schema introspection for ShotGrid entities. Cached for performance.

## Tools

| Tool | Intent |
|------|--------|
| `get_schema` | Get full schema for all entity types |
| `get_field_schema` | Get field definitions for a specific entity type |
| `list_entity_types` | List all available entity types (from schema cache) |

## After Success

- `get_schema` returns full schema cache.
- `get_field_schema` returns individual fields with types, constraints, valid values.
- Use field info to construct valid filters and data for CRUD operations.

## After Failure

- Check connection via `shotgrid-discovery__check_connection`.
- Schema is cached for 1 hour; use `get_schema` to force refresh.
