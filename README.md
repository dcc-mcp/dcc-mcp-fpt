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
```

### Run

**HTTP mode:**
```bash
dcc-mcp-fpt http --host 0.0.0.0 --port 8765
# MCP endpoint: http://localhost:8765/mcp
```

**stdio mode (for Claude Desktop):**
```bash
dcc-mcp-fpt stdio
```

**ASGI mode (for uvicorn/gunicorn):**
```bash
uvicorn dcc_mcp_fpt.asgi:app --host 0.0.0.0 --port 8000
```

**Docker:**
```bash
docker run --rm -p 8765:8765 \
    -e SHOTGRID_URL="$SHOTGRID_URL" \
    -e SHOTGRID_SCRIPT_NAME="$SHOTGRID_SCRIPT_NAME" \
    -e SHOTGRID_SCRIPT_KEY="$SHOTGRID_SCRIPT_KEY" \
    dcc-mcp-fpt
```

### Claude Desktop Config

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "shotgrid": {
      "command": "uvx",
      "args": ["dcc-mcp-fpt", "stdio"],
      "env": {
        "SHOTGRID_URL": "https://mysite.shotgrid.autodesk.com",
        "SHOTGRID_SCRIPT_NAME": "my_script_name",
        "SHOTGRID_SCRIPT_KEY": "my_script_key"
      }
    }
  }
}
```

## Tool Surface

### Bootstrap (eager-loaded)
| Skill | Tools |
|-------|-------|
| `shotgrid-discovery` | `check_connection`, `list_entity_types`, `get_server_info` |
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
| `DCC_MCP_SHOTGRID_MINIMAL` | No | Comma-separated minimal mode skill list |
| `DCC_MCP_SHOTGRID_DEFAULT_TOOLS` | No | Comma-separated default tools to activate |

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

## Requirements

- Python 3.8+
- [dcc-mcp-core](https://github.com/dcc-mcp/dcc-mcp-core) >= 0.17.54
- [shotgun_api3](https://github.com/shotgunsoftware/python-api) >= 3.4.0

## License

MIT — see [LICENSE](LICENSE).

## Related

- [dcc-mcp-core](https://github.com/dcc-mcp/dcc-mcp-core) — Core runtime and shared tooling
- [shotgrid-mcp-server](https://github.com/loonghao/shotgrid-mcp-server) — Original FastMCP-based implementation
- [dcc-mcp-maya](https://github.com/dcc-mcp/dcc-mcp-maya) — Maya adapter reference
- [dcc-mcp-blender](https://github.com/dcc-mcp/dcc-mcp-blender) — Blender adapter reference
