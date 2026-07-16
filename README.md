# dcc-mcp-fpt

**ShotGrid (Flow Production Tracking) adapter for the DCC-MCP ecosystem.**

[![CI](https://github.com/dcc-mcp/dcc-mcp-fpt/actions/workflows/ci.yml/badge.svg)](https://github.com/dcc-mcp/dcc-mcp-fpt/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)]()

Bridges AI assistants (Claude, Cursor, VS Code Copilot) to ShotGrid data through
typed, progressively-loaded MCP tools built on [dcc-mcp-core](https://github.com/dcc-mcp/dcc-mcp-core).

> This is a fresh re-implementation of the [shotgrid-mcp-server](https://github.com/loonghao/shotgrid-mcp-server)
> using the dcc-mcp framework — providing the same ShotGrid integration surface
> with gateway routing, skill-based progressive loading, and multi-DCC
> observability built in.

## Why Use It

| Feature | Description |
|---------|-------------|
| **20+ Typed Tools** | CRUD, search, batch, notes, schema — all with validated schemas |
| **Progressive Loading** | Bootstrap tools eager-loaded; advanced tools loaded on demand |
| **Gateway Ready** | Plugs into the dcc-mcp gateway for unified multi-service routing |
| **Skill-First** | Every tool is a typed skill with `tools.yaml`, schemas, and annotations |
| **Connection Pooling** | Reuses authenticated sessions for performance |
| **Schema Caching** | Entity field schemas cached with configurable TTL |
| **Multi-Transport** | stdio, HTTP, and ASGI — works anywhere |
| **Docker Ready** | Single-command container deployment |

## Quick Start

### Install

```bash
pip install dcc-mcp-fpt
```

Or with uv:
```bash
uv pip install dcc-mcp-fpt
```

### Configure

Set your ShotGrid credentials:

```bash
export SHOTGRID_URL="https://mysite.shotgrid.autodesk.com"
export SHOTGRID_SCRIPT_NAME="my_script_name"
export SHOTGRID_SCRIPT_KEY="my_script_key"
export SHOTGRID_PROJECT="my_project_code"
export SHOTGRID_PERMISSION_LEVEL="read"
```

### Run Locally

The shortest local path is:

```bash
uvx dcc-mcp-fpt
```

By default the adapter binds an OS-assigned instance port and enables
the stable local gateway at `http://127.0.0.1:9765/mcp`. Use
`dcc-mcp-cli list` to inspect the direct endpoint. If a healthy gateway is
already running on that port, this FPT adapter registers into it; otherwise the
core gateway election path can own the gateway port for the local session.

Use standalone mode only when you do not want gateway registration:

```bash
uvx dcc-mcp-fpt --no-gateway
# Same as: uvx dcc-mcp-fpt --gateway-port 0
```

Development checkout:

```bash
python -m dcc_mcp_fpt
just serve-gateway
just serve-standalone
```

ASGI mode for uvicorn/gunicorn remains available:

```bash
uvicorn dcc_mcp_fpt.asgi:app --host 0.0.0.0 --port 8000
```

### IDE MCP Config

For IDEs that support Streamable HTTP MCP, point the IDE at the gateway URL:

```json
{
  "mcpServers": {
    "shotgrid": {
      "url": "http://127.0.0.1:9765/mcp"
    }
  }
}
```

If your IDE only supports stdio MCP, use `uvx` directly:

```json
{
  "mcpServers": {
    "shotgrid": {
      "command": "uvx",
      "args": ["dcc-mcp-fpt", "stdio", "--no-gateway"],
      "env": {
        "SHOTGRID_URL": "https://mysite.shotgrid.autodesk.com",
        "SHOTGRID_SCRIPT_NAME": "my_script_name",
        "SHOTGRID_SCRIPT_KEY": "my_script_key",
        "SHOTGRID_PROJECT": "my_project_code",
        "SHOTGRID_PERMISSION_LEVEL": "read"
      }
    }
  }
}
```

### mcpcall

After `uvx dcc-mcp-fpt` is running, smoke-test through the gateway:

```bash
mcpcall doctor --url http://127.0.0.1:9765/mcp --json
mcpcall list --url http://127.0.0.1:9765/mcp --json
mcpcall call --url http://127.0.0.1:9765/mcp shotgrid-discovery__check_connection
mcpcall call --url http://127.0.0.1:9765/mcp shotgrid-discovery__get_server_info
```

You can also import the same `mcpServers` JSON used by your IDE:

```bash
mcpcall config import --from ./mcp.json --output ./mcpcall.json
mcpcall list --config ./mcpcall.json --server shotgrid --json
```

## Tool Surface

### Bootstrap (eager-loaded)
| Skill | Tools |
|-------|-------|
| `shotgrid-discovery` | `check_connection`, `list_entity_types`, `get_server_info` |
| `shotgrid-setup` | `generate_agent_config`, `validate_runtime_config` |
| `shotgrid-users` | `whoami` |
| `shotgrid-schema` | `get_schema`, `get_field_schema`, `list_entity_types` |

### Scene (loaded on demand)
| Skill | Tools |
|-------|-------|
| `shotgrid-crud` | `find_entities`, `find_one_entity`, `create_entity`, `update_entity`, `delete_entity` |
| `shotgrid-search` | `search_entities`, `search_by_name` |

### Authoring
| Skill | Tools |
|-------|-------|
| `shotgrid-note` | `create_note`, `find_notes`, `update_note` |

### Pipeline
| Skill | Tools |
|-------|-------|
| `shotgrid-batch` | `batch_operations` |

## Architecture

```
AI Agent (Claude, Cursor, Copilot)
        │
        │ MCP Protocol (stdio / HTTP / ASGI)
        ▼
┌───────────────────────────────┐
│     ShotGridMcpServer         │
│   (DccServerBase adapter)     │
│                               │
│  ┌─────────────────────────┐  │
│  │   Skill Catalog          │  │
│  │  (progressive loading)   │  │
│  └───────────┬─────────────┘  │
│              │                │
│  ┌───────────▼─────────────┐  │
│  │   HostExecutionBridge    │  │
│  │   → ShotGridClient       │  │
│  └───────────┬─────────────┘  │
│              │                │
│  ┌───────────▼─────────────┐  │
│  │  ConnectionPool          │  │
│  │  SchemaCache             │  │
│  └───────────┬─────────────┘  │
└──────────────┼────────────────┘
               │
               │ shotgun_api3 (REST)
               ▼
     ┌─────────────────┐
     │  ShotGrid API    │
     │  (Autodesk FPT)  │
     └─────────────────┘
```

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `SHOTGRID_URL` | Yes | ShotGrid server URL |
| `SHOTGRID_SCRIPT_NAME` | Yes | Script/API user name |
| `SHOTGRID_SCRIPT_KEY` | Yes | Script/API user key |
| `SHOTGRID_PROJECT` | No | Default project name, code, or tank name for scoped tools |
| `SHOTGRID_PROJECT_ID` | No | Default project ID; overrides `SHOTGRID_PROJECT` when set |
| `SHOTGRID_PERMISSION_LEVEL` | No | Fallback permission level: `read`, `write`, or `admin` |
| `SHOTGRID_PROJECT_PERMISSIONS` | No | JSON or CSV per-project permission allowlist |
| `SHOTGRID_READ_ONLY` | No | Set to `1` to block create/update/delete regardless of level |
| `DCC_MCP_GATEWAY_PORT` | No | dcc-mcp gateway port; set `0` to run standalone |
| `DCC_MCP_REGISTRY_DIR` | No | Shared gateway registry directory |
| `DCC_MCP_FPT_GATEWAY_SCENE` | No | Gateway context label; defaults to `project:<SHOTGRID_PROJECT>` |
| `DCC_MCP_FPT_GATEWAY_DISPLAY_NAME` | No | Human-readable label shown in gateway/admin surfaces |
| `DCC_MCP_FPT_ENABLE_GATEWAY_FAILOVER` | No | Set `0` to disable core gateway election/failover |
| `DCC_MCP_FPT_SKILL_PATHS` | No | FPT-specific custom skill roots (`;` on Windows, `:` on Unix) |
| `DCC_MCP_SKILL_PATHS` | No | Global custom skill roots shared by all dcc-mcp adapters |
| `DCC_MCP_SHOTGRID_MINIMAL` | No | Comma-separated minimal mode skill list |
| `DCC_MCP_SHOTGRID_DEFAULT_TOOLS` | No | Comma-separated default tools to activate |

### Project Scoping and Permissions

CRUD and batch tools accept optional `project`, `project_id`, and
`project_scoped` inputs. When a default project is configured, reads add a
ShotGrid `project` filter, creates inject `data.project` when missing, and
updates/deletes validate project ownership before mutating data.

Permission levels are intentionally simple:

| Level | Allows |
|-------|--------|
| `read` | `find`, `find_one`, schema, connection checks |
| `write` | `read` plus create/update and non-delete batch items |
| `admin` | `write` plus delete/retire |

Examples:

```bash
export SHOTGRID_PROJECT="my_project_code"
export SHOTGRID_PERMISSION_LEVEL="write"
export SHOTGRID_PROJECT_PERMISSIONS='{"my_project_code":"write","id:456":"read"}'
```

### Gateway Integration

The adapter uses the same `DccServerOptions.from_env(...)` gateway contract as
the Maya, Blender, Houdini, and 3ds Max adapters. When `DCC_MCP_GATEWAY_PORT`
or `--gateway-port` is set to a positive value, the server publishes an FPT
runtime entry with a safe display name, project-aware scene label, version, and
gateway election diagnostics.

```bash
export SHOTGRID_PROJECT="my_project_code"
export DCC_MCP_GATEWAY_PORT=9765
export DCC_MCP_FPT_GATEWAY_DISPLAY_NAME="FPT my_project_code"

just serve-gateway
```

Use `--gateway-port 0` or `just serve-standalone` for local standalone testing.
The `shotgrid-discovery__get_server_info` tool includes a `gateway` diagnostics
object so agents and CI can confirm whether this instance joined the gateway.

### Request-Scoped Credentials

HTTP MCP clients do not inject `mcp.json.env` into an already-running Gateway.
For shared Gateway deployments, keep ShotGrid secrets in adapter-side profiles
and pass request context through MCP `_meta`. With core PIP-520, caller identity
lives under `_meta.agent_context`, while credential and policy controls are
bounded top-level `_meta` fields:

```json
{
  "_meta": {
    "agent_context": {
      "requester_id": "hallong",
      "requester_type": "human"
    },
    "credential_profile": "sg-read-zombie",
    "permission_hint": "read",
    "project_scope": "my_project_code"
  }
}
```

Legacy clients that still send `credential_profile`, `permission_hint`, or
`project_scope` inside `_meta.agent_context` remain supported as a fallback, but
new agents should use the PIP-520 top-level `_meta` shape above.

Profiles can be supplied as JSON in `DCC_MCP_FPT_CREDENTIAL_PROFILES` or from a
JSON file via `DCC_MCP_FPT_CREDENTIAL_PROFILES_FILE`:

```json
{
  "sg-read-zombie": {
    "url": "https://mysite.shotgrid.autodesk.com",
    "script_name": "sg_read_bot",
    "script_key": "<secret stored outside chat>",
    "permission_level": "read",
    "read_only": true,
    "project": "my_project_code"
  }
}
```

`permission_hint` can only reduce the effective policy. It is merged with the
env/profile policy by minimum permission, so an agent cannot turn a read profile
into write/admin. Inline credentials are rejected unless
`DCC_MCP_ALLOW_INLINE_CREDENTIALS=1` is set for local development.

### Agent Setup Skill

`shotgrid-setup` is eager-loaded so agents can bootstrap configuration without
guessing repo conventions:

```bash
mcpcall call --url http://127.0.0.1:9765/mcp shotgrid-setup__validate_runtime_config
mcpcall call --url http://127.0.0.1:9765/mcp shotgrid-setup__generate_agent_config target=all
```

The generated config includes `uvx dcc-mcp-fpt`, HTTP/stdio IDE snippets,
mcpcall commands, Docker examples, and custom skill path environment variables.
Secret values are redacted by default.

### Custom Skills

Point `DCC_MCP_FPT_SKILL_PATHS` at a skill package directory or a parent
directory containing multiple skill package folders:

```bash
# Windows uses semicolon between multiple roots.
set DCC_MCP_FPT_SKILL_PATHS=C:\studio\fpt-skills;C:\show\fpt-skills

# Linux/macOS uses colon.
export DCC_MCP_FPT_SKILL_PATHS=/studio/fpt-skills:/show/fpt-skills

uvx dcc-mcp-fpt
```

Use `DCC_MCP_SKILL_PATHS` for shared cross-adapter skills. The gateway admin
skill path registry is also picked up by dcc-mcp-core on startup/reload.

### Container Deployment

Build and run locally:

```bash
docker build -t dcc-mcp-fpt .
docker run --rm \
  -p 9765:9765 \
  --env-file .env \
  dcc-mcp-fpt
```

Inject custom skills by mounting a directory to `/skills`; the image sets
`DCC_MCP_FPT_SKILL_PATHS=/skills` by default:

```bash
docker run --rm \
  -p 9765:9765 \
  --env-file .env \
  -v /studio/fpt-skills:/skills:ro \
  dcc-mcp-fpt
```

Docker Compose (includes health check and graceful shutdown):

```bash
docker compose -f docker-compose.yml up -d
```

For per-user credential profiles, use the profiles overlay:

```bash
# 1. Create fpt-credential-profiles.json (see Per-User Access below)
# 2. Launch with profiles compose file
docker compose -f docker-compose.yml -f docker-compose.profiles.yml up -d
```

### Health Check

The stable gateway exposes `/health` for container probes and platform monitoring:

```bash
curl http://localhost:9765/health
# {"status": "ok", "version": "dcc-mcp-fpt/0.1.2", "sg_configured": true}
```

- `sg_configured: true` means ShotGrid credentials are available.
- No secrets are exposed — the field is a boolean derived from the presence of `SHOTGRID_URL`.
- The endpoint works even when `dcc-mcp-core` is not installed.

### Agent Platform Deployment

The adapter is designed to run on OpenClaw, Harness, and other MCP-compatible
agent platforms. See `deployment/OPENCLAW.md` and `deployment/HARNESS.md` for
platform-specific configuration guides.

Key platform features:
- **Graceful shutdown**: Handles `SIGTERM` for clean orchestrated stops.
- **Health endpoint**: `/health` for Kubernetes liveness/readiness probes.
- **Stateless + profiles**: Deploy one instance; select credentials per-request via `_meta`.
- **Gateway registration**: Optionally joins the dcc-mcp gateway for unified routing.

### Per-User Access with whoami

The `shotgrid-users` skill provides a `whoami` tool that reports the effective
ShotGrid identity without exposing secrets. Use it to confirm which credential
profile and permission level is active:

```bash
mcpcall call --url http://127.0.0.1:9765/mcp shotgrid-users__whoami
```

With a request-scoped profile:

```bash
mcpcall call --url http://127.0.0.1:9765/mcp shotgrid-users__whoami \
  --meta '{"credential_profile":"sg-read-zombie","project_scope":"demo"}'
```

The response includes `script_name`, `url`, `permission_level`, `credential_profile`,
and `credential_source` — but never the `api_key`.

## Development

```bash
git clone https://github.com/dcc-mcp/dcc-mcp-fpt.git
cd dcc-mcp-fpt

# Install with dev deps
uv pip install -e ".[dev]"

# Run tests
pytest --cov=src/dcc_mcp_fpt --cov-report=term

# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/
```

### Local Live CRUD Smoke

Copy `.env.example` to `.env`, fill in local credentials, and keep the file
untracked. The dry-run command verifies configuration and skips mutations:

```bash
just install-dev
just live-crud-smoke-dry
```

To run a real local create/find/update/delete cycle against the configured
project, set an admin-capable policy for that project and run:

```bash
export SHOTGRID_PERMISSION_LEVEL="admin"
export SHOTGRID_LIVE_CRUD_CONFIRM=1
just live-crud-smoke
```

The smoke creates a temporary entity, updates it, and retires it on cleanup.

## CI/CD

- `CI` runs Python 3.8-3.12 across Linux, Windows, and macOS.
- Lint, format check, bundled skill metadata lint, CLI smoke, package build,
  and Docker build are separate gates.
- `Release` uses release-please, builds wheel/sdist artifacts, publishes via
  PyPI Trusted Publishing, and attaches the dist files to the GitHub Release.
- `Live ShotGrid Smoke` is manual-only and uses GitHub Secrets; it defaults to
  dry-run behavior unless CRUD confirmation is enabled.
- E2E tests cover all 8 skill packages, server lifecycle, health endpoint,
  credential profile file loading, and permission policy resolution.

## Requirements

- Python 3.8+
- [dcc-mcp-core](https://github.com/dcc-mcp/dcc-mcp-core) >= 0.18.2,<1.0.0
- [shotgun_api3](https://github.com/shotgunsoftware/python-api) >= 3.4.0

## License

MIT — see [LICENSE](LICENSE).

## Related

- [dcc-mcp-core](https://github.com/dcc-mcp/dcc-mcp-core) — Core runtime and shared tooling
- [shotgrid-mcp-server](https://github.com/loonghao/shotgrid-mcp-server) — Original FastMCP-based implementation
- [dcc-mcp-maya](https://github.com/dcc-mcp/dcc-mcp-maya) — Maya adapter reference
- [dcc-mcp-blender](https://github.com/dcc-mcp/dcc-mcp-blender) — Blender adapter reference
