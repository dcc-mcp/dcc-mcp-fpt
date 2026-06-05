# Deploying dcc-mcp-fpt on OpenClaw

dcc-mcp-fpt can be deployed as a persistent MCP service on the OpenClaw agent
platform. This guide covers setup, configuration, and agent integration.

## Prerequisites

- A running OpenClaw instance (or OpenClaw-compatible MCP endpoint)
- ShotGrid credentials (script name + key, or a credential profiles file)
- Docker (recommended) or Python 3.8+

## Quick Start (Docker)

```bash
# Build and run
docker build -t dcc-mcp-fpt .
docker run --rm \
  -p 8765:8765 \
  -p 9765:9765 \
  --env-file .env \
  --stop-signal SIGTERM \
  dcc-mcp-fpt
```

Or with docker-compose:

```bash
docker compose -f docker-compose.yml up -d
```

### Health Check

The adapter exposes a `/health` endpoint at port 8765:

```bash
curl http://localhost:8765/health
# {"status": "ok", "version": "dcc-mcp-fpt/0.1.2", "sg_configured": true}
```

OpenClaw can use this endpoint for readiness/liveness probes.

## MCP Endpoint

Once running, the MCP endpoint is available at:

```
http://<host>:8765/mcp
```

If the dcc-mcp gateway is enabled, also at:

```
http://<host>:9765/mcp
```

Configure OpenClaw to point at either URL.

## Per-User ShotGrid Access

The adapter supports request-scoped credential switching via MCP `_meta`.
This allows multiple users on the same OpenClaw instance to use different
ShotGrid accounts.

### 1. Configure Credential Profiles

Create a `fpt-credential-profiles.json` file:

```json
{
  "sg-read-zombie": {
    "url": "https://mysite.shotgrid.autodesk.com",
    "script_name": "sg_read_bot",
    "script_key": "<SECRET>",
    "permission_level": "read",
    "read_only": true,
    "project": "demo_project"
  },
  "sg-write-artist": {
    "url": "https://mysite.shotgrid.autodesk.com",
    "script_name": "sg_write_bot",
    "script_key": "<SECRET>",
    "permission_level": "write",
    "project": "demo_project"
  }
}
```

### 2. Mount Profiles

**Docker with secrets:**

```bash
docker compose -f docker-compose.yml -f docker-compose.profiles.yml up -d
```

**Environment variable:**

Set `DCC_MCP_FPT_CREDENTIAL_PROFILES` or `DCC_MCP_FPT_CREDENTIAL_PROFILES_FILE`
in the container environment.

### 3. Pass Context via MCP _meta

When an agent tool is invoked via OpenClaw, include `_meta` in the MCP request:

```json
{
  "_meta": {
    "agent_context": {
      "requester_id": "hallong",
      "requester_type": "human"
    },
    "credential_profile": "sg-read-zombie",
    "permission_hint": "read",
    "project_scope": "demo_project"
  }
}
```

The `whoami` tool reports which profile and permission level is active:

```
mcpcall call --url http://127.0.0.1:8765/mcp shotgrid-users__whoami
```

### 4. Profile Resolution Order

1. `credential_profile` in `_meta` → loads matching profile from file/env
2. Inline `credentials` in agent context (requires `DCC_MCP_ALLOW_INLINE_CREDENTIALS=1` for dev only)
3. Environment variables (`SHOTGRID_URL`, `SHOTGRID_SCRIPT_NAME`, `SHOTGRID_SCRIPT_KEY`) as default

## Gateway Integration

When `DCC_MCP_GATEWAY_PORT` is set (default 9765), the adapter registers into
the dcc-mcp gateway. Multiple adapters (Maya, Blender, FPT) can co-exist
behind a single gateway port for unified routing.

```yaml
environment:
  - DCC_MCP_GATEWAY_PORT=9765
  - DCC_MCP_FPT_GATEWAY_DISPLAY_NAME="FPT demo_project"
  - DCC_MCP_FPT_ENABLE_GATEWAY_FAILOVER=1
```

Set `--gateway-port 0` or `DCC_MCP_GATEWAY_PORT=0` for standalone mode.

## Environment Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `SHOTGRID_URL` | Yes* | ShotGrid server URL |
| `SHOTGRID_SCRIPT_NAME` | Yes* | Script/API user name |
| `SHOTGRID_SCRIPT_KEY` | Yes* | Script/API user key |
| `SHOTGRID_PROJECT` | No | Default project scope |
| `SHOTGRID_PROJECT_ID` | No | Default project ID |
| `SHOTGRID_PERMISSION_LEVEL` | No | `read`, `write`, or `admin` |
| `SHOTGRID_READ_ONLY` | No | Set `1` to block mutations |
| `DCC_MCP_FPT_CREDENTIAL_PROFILES` | No | JSON profiles for per-user access |
| `DCC_MCP_FPT_CREDENTIAL_PROFILES_FILE` | No | Path to profiles JSON file |
| `DCC_MCP_GATEWAY_PORT` | No | Gateway port (0=standalone) |
| `DCC_MCP_FPT_GATEWAY_DISPLAY_NAME` | No | Gateway display label |
| `DCC_MCP_FPT_ENABLE_GATEWAY_FAILOVER` | No | Gateway election/failover |

\* Not required if using credential profiles.
