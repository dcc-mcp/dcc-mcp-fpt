---
name: shotgrid-setup
description: >-
  ShotGrid setup skill - generate local IDE, mcpcall, Docker, gateway, and
  custom skill injection configuration for dcc-mcp-fpt. Use when an agent needs
  to help a user bootstrap or audit a local/container deployment.
license: MIT
compatibility: "Python 3.8+; dcc-mcp-core 0.17+"
allowed-tools: Bash Read Write Edit
metadata:
  dcc-mcp:
    dcc: shotgrid
    version: "0.1.0"
    layer: thin-harness
    stage: bootstrap
    tags: ["setup", "gateway", "ide", "docker", "mcpcall", "skills"]
    search-hint: "configure dcc-mcp-fpt, uvx, gateway, IDE MCP config, mcpcall, Docker, custom skills"
    tools: tools.yaml
---

# ShotGrid Setup

Eager-loaded at startup. Helps agents configure dcc-mcp-fpt for local
development, IDE MCP clients, mcpcall smoke tests, containers, and custom skill
paths.

## Tools

| Tool | Intent |
|------|--------|
| `generate_agent_config` | Produce local command, MCP config snippets, mcpcall commands, Docker examples, and skill path environment hints |
| `validate_runtime_config` | Inspect current environment for required ShotGrid, gateway, permission, and custom skill path settings |

## Guidance

- Prefer `uvx dcc-mcp-fpt` for local HTTP startup. It uses the default gateway
  port `9765`; if a resident gateway is already healthy, this adapter joins it.
- Use `--no-gateway` or `--gateway-port 0` only for standalone debugging.
- Do not persist secret values unless the user explicitly asks. This skill
  redacts `SHOTGRID_SCRIPT_KEY` by default.
