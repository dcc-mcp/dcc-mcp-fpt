# dcc-mcp-fpt

**ShotGrid (Flow Production Tracking) 的 DCC-MCP 生态系统适配器。**

[![CI](https://github.com/dcc-mcp/dcc-mcp-fpt/actions/workflows/ci.yml/badge.svg)](https://github.com/dcc-mcp/dcc-mcp-fpt/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)]()

通过构建在 [dcc-mcp-core](https://github.com/dcc-mcp/dcc-mcp-core) 上的类型化、
渐进式加载的 MCP 工具，将 AI 助手（Claude、Cursor、VS Code Copilot）桥接到
ShotGrid 数据。

> 这是 [shotgrid-mcp-server](https://github.com/loonghao/shotgrid-mcp-server) 的
> 全新实现，使用 dcc-mcp 框架 — 提供相同的 ShotGrid 集成能力，并额外内置了
> 网关路由、基于技能的渐进式加载和多 DCC 可观测性。

## 为什么选择

| 特性 | 描述 |
|------|------|
| **20+ 类型化工具** | CRUD、搜索、批量操作、笔记、Schema — 全部带有验证 Schema |
| **渐进式加载** | 启动时加载核心工具；高级工具按需加载 |
| **网关就绪** | 接入 dcc-mcp 网关实现统一的多服务路由 |
| **技能优先** | 每个工具都是带有 `tools.yaml`、Schema 和注释的类型化技能 |
| **连接池** | 复用已验证的会话以提升性能 |
| **Schema 缓存** | 实体字段 Schema 缓存，TTL 可配置 |
| **多传输模式** | stdio、HTTP 和 ASGI — 可在任何环境运行 |
| **Docker 支持** | 单命令容器部署 |

## 快速开始

### 安装

```bash
pip install dcc-mcp-fpt
```

或使用 uv：
```bash
uv pip install dcc-mcp-fpt
```

### 配置

设置您的 ShotGrid 凭证：

```bash
export SHOTGRID_URL="https://mysite.shotgrid.autodesk.com"
export SHOTGRID_SCRIPT_NAME="my_script_name"
export SHOTGRID_SCRIPT_KEY="my_script_key"
```

### 运行

**HTTP 模式：**
```bash
dcc-mcp-fpt http --host 0.0.0.0 --port 8765
# MCP 端点: http://localhost:8765/mcp
```

**stdio 模式（用于 Claude Desktop）：**
```bash
dcc-mcp-fpt stdio
```

**ASGI 模式（用于 uvicorn/gunicorn）：**
```bash
uvicorn dcc_mcp_fpt.asgi:app --host 0.0.0.0 --port 8000
```

**Docker：**
```bash
docker run --rm -p 8765:8765 \
    -e SHOTGRID_URL="$SHOTGRID_URL" \
    -e SHOTGRID_SCRIPT_NAME="$SHOTGRID_SCRIPT_NAME" \
    -e SHOTGRID_SCRIPT_KEY="$SHOTGRID_SCRIPT_KEY" \
    dcc-mcp-fpt
```

### Claude Desktop 配置

添加到 `claude_desktop_config.json`：

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

## 工具概览

### 启动时加载
| 技能 | 工具 |
|------|------|
| `shotgrid-discovery` | `check_connection`, `list_entity_types`, `get_server_info` |
| `shotgrid-schema` | `get_schema`, `get_field_schema`, `list_entity_types` |

### 按需加载
| 技能 | 工具 |
|------|------|
| `shotgrid-crud` | `find_entities`, `find_one_entity`, `create_entity`, `update_entity`, `delete_entity` |
| `shotgrid-search` | `search_entities`, `search_by_name` |
| `shotgrid-note` | `create_note`, `find_notes`, `update_note` |
| `shotgrid-batch` | `batch_operations` |

## 架构

```
AI 助手 (Claude, Cursor, Copilot)
        │
        │ MCP 协议 (stdio / HTTP / ASGI)
        ▼
┌───────────────────────────────┐
│     ShotGridMcpServer         │
│   (DccServerBase 适配器)      │
│                               │
│  ┌─────────────────────────┐  │
│  │   技能目录                │  │
│  │  (渐进式加载)             │  │
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

## 环境变量

| 变量 | 必填 | 描述 |
|------|------|------|
| `SHOTGRID_URL` | 是 | ShotGrid 服务器 URL |
| `SHOTGRID_SCRIPT_NAME` | 是 | Script/API 用户名 |
| `SHOTGRID_SCRIPT_KEY` | 是 | Script/API 密钥 |
| `DCC_MCP_SHOTGRID_MINIMAL` | 否 | 逗号分隔的最小模式技能列表 |
| `DCC_MCP_SHOTGRID_DEFAULT_TOOLS` | 否 | 逗号分隔的默认激活工具 |

## 本地开发

```bash
git clone https://github.com/dcc-mcp/dcc-mcp-fpt.git
cd dcc-mcp-fpt

# 安装开发依赖
uv pip install -e ".[dev]"

# 运行测试
pytest --cov=src/dcc_mcp_fpt --cov-report=term

# 代码检查
ruff check src/ tests/

# 格式化代码
ruff format src/ tests/
```

## 依赖

- Python 3.8+
- [dcc-mcp-core](https://github.com/dcc-mcp/dcc-mcp-core) >= 0.17.54
- [shotgun_api3](https://github.com/shotgunsoftware/python-api) >= 3.4.0

## 许可证

MIT — 详见 [LICENSE](LICENSE)。

## 相关项目

- [dcc-mcp-core](https://github.com/dcc-mcp/dcc-mcp-core) — 核心运行时和共享工具
- [shotgrid-mcp-server](https://github.com/loonghao/shotgrid-mcp-server) — 原始 FastMCP 实现
- [dcc-mcp-maya](https://github.com/dcc-mcp/dcc-mcp-maya) — Maya 适配器参考
- [dcc-mcp-blender](https://github.com/dcc-mcp/dcc-mcp-blender) — Blender 适配器参考
