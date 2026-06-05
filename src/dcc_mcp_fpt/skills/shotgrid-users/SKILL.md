---
name: shotgrid-users
description: >-
  ShotGrid user identity skill — report effective credentials, permission level,
  and active profile without exposing secrets. Use when an agent needs to know
  whose ShotGrid account is in use.
license: MIT
compatibility: "Python 3.8+; dcc-mcp-core 0.18.2+"
allowed-tools: Bash Read Write Edit
metadata:
  dcc-mcp:
    dcc: shotgrid
    version: "0.1.0"
    layer: thin-harness
    stage: bootstrap
    tags: ["identity", "whoami", "bootstrap", "shotgrid"]
    search-hint: "whoami, current user, credentials profile, permission level"
    tools: tools.yaml
---

# ShotGrid Users

Eager-loaded at startup. Reports the effective ShotGrid identity — script
name, server URL, permission level, and active credential profile — without
ever exposing secrets.

## Tools

| Tool | Intent |
|------|--------|
| `whoami` | Report effective credentials, permission level, and active profile |

## After Success

- Agent sees the ShotGrid URL, script name, permission level, and which
  credential profile (if any) is active.
- Agent can use this to confirm it is operating with the expected access
  level before running CRUD or search operations.

## After Failure

- If `whoami` returns `authenticated: false`, verify ShotGrid credentials
  in the profile or environment configuration.
