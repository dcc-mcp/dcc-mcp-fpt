---
name: shotgrid-search
description: >-
  ShotGrid search skill — advanced entity search with text matching, relationship
  traversal, and filter composition. Use when an AI agent needs to find entities
  by name, status, dates, or relationships beyond simple field equality.
  Not for single-entity CRUD — use shotgrid-crud for that.
license: MIT
compatibility: "Python 3.8+; dcc-mcp-core 0.17+"
allowed-tools: Bash Read Write Edit
metadata:
  dcc-mcp:
    dcc: shotgrid
    version: "0.1.0"
    layer: domain
    stage: scene
    tags: ["search", "query", "filter", "text-search", "shotgrid"]
    search-hint: "search shotgrid entities, text search, filter shots, find by name, complex query"
    tools: tools.yaml
---

# ShotGrid Search

Advanced entity search combining text search, relationship filters,
and complex filter expressions.

## Tools

| Tool | Intent |
|------|--------|
| `search_entities` | Full-text and filter-based entity search |
| `search_by_name` | Convenience search by entity code/name field |

## After Success

- `search_entities` returns matching entities with pagination.
- `search_by_name` returns entities whose `code` or `name` matches.

## After Failure

- Verify entity type exists via `shotgrid-discovery__list_entity_types`.
- Check schema via `shotgrid-schema__get_field_schema`.
