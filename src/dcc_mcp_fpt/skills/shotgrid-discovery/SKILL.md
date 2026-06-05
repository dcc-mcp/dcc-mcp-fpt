---
name: shotgrid-discovery
description: >-
  ShotGrid discovery skill — verify connection, list entity types, and inspect
  server info. Use when an AI agent needs to understand available ShotGrid data
  before querying specific entities. Not for CRUD operations or schema details.
license: MIT
compatibility: "Python 3.8+; dcc-mcp-core >=0.18.2,<1.0.0"
allowed-tools: Bash Read Write Edit
metadata:
  dcc-mcp:
    dcc: shotgrid
    version: "0.1.0"
    layer: thin-harness
    stage: bootstrap
    tags: ["discovery", "connection", "bootstrap", "shotgrid"]
    search-hint: "check shotgrid connection, list entity types, server info, ping"
    tools: tools.yaml
---

# ShotGrid Discovery

Eager-loaded at startup. Provides the minimal surface an agent needs to
orient itself: verify the ShotGrid connection, list available entity types,
and inspect server version.

## Tools

| Tool | Intent |
|------|--------|
| `check_connection` | Verify ShotGrid credentials and connectivity |
| `list_entity_types` | List all entity types visible to the script user |
| `get_server_info` | Return ShotGrid server version and metadata |

## After Success

- Agent should see `authenticated: true` from `check_connection`.
- `list_entity_types` should return entity type names the agent can use
  with `shotgrid-crud` and `shotgrid-search` tools.

## After Failure

- If `check_connection` returns `authenticated: false`, verify
  `SHOTGRID_URL`, `SHOTGRID_SCRIPT_NAME`, and `SHOTGRID_SCRIPT_KEY`
  environment variables.
