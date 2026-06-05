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
export SHOTGRID_PROJECT="my_project_code"
export SHOTGRID_PERMISSION_LEVEL="read"
```

### 本地启动

最短的本地启动方式：

```bash
uvx dcc-mcp-fpt
```

默认会启动适配器端点 `http://127.0.0.1:8765/mcp`，并在
`http://127.0.0.1:9765/mcp` 启用 dcc-mcp gateway。如果 9765 上已经有健康的
gateway，FPT 适配器会注册进去一起工作；如果没有，core 的 gateway 选举路径可以
在当前本地会话里持有该端口。

只有在不希望注册 gateway 时才使用独立模式：

```bash
uvx dcc-mcp-fpt --no-gateway
# 等价于: uvx dcc-mcp-fpt --gateway-port 0
```

开发 checkout 下也可以使用：

```bash
python -m dcc_mcp_fpt
just serve-gateway
just serve-standalone
```

ASGI 模式仍然可用于 uvicorn/gunicorn：

```bash
uvicorn dcc_mcp_fpt.asgi:app --host 0.0.0.0 --port 8000
```

### IDE MCP 配置

如果 IDE 支持 Streamable HTTP MCP，直接指向 gateway URL：

```json
{
  "mcpServers": {
    "shotgrid": {
      "url": "http://127.0.0.1:9765/mcp"
    }
  }
}
```

如果 IDE 只支持 stdio MCP，可以使用 `uvx`：

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

`uvx dcc-mcp-fpt` 启动后，可以通过 gateway 做 smoke：

```bash
mcpcall doctor --url http://127.0.0.1:9765/mcp --json
mcpcall list --url http://127.0.0.1:9765/mcp --json
mcpcall call --url http://127.0.0.1:9765/mcp shotgrid-discovery__check_connection
mcpcall call --url http://127.0.0.1:9765/mcp shotgrid-discovery__get_server_info
```

也可以复用 IDE 的 `mcpServers` JSON：

```bash
mcpcall config import --from ./mcp.json --output ./mcpcall.json
mcpcall list --config ./mcpcall.json --server shotgrid --json
```

## 工具概览

### 启动时加载
| 技能 | 工具 |
|------|------|
| `shotgrid-discovery` | `check_connection`, `list_entity_types`, `get_server_info` |
| `shotgrid-setup` | `generate_agent_config`, `validate_runtime_config` |
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
| `SHOTGRID_PROJECT` | 否 | 默认项目名称、代码或 tank name |
| `SHOTGRID_PROJECT_ID` | 否 | 默认项目 ID；设置后优先于 `SHOTGRID_PROJECT` |
| `SHOTGRID_PERMISSION_LEVEL` | 否 | 默认权限级别：`read`、`write` 或 `admin` |
| `SHOTGRID_PROJECT_PERMISSIONS` | 否 | JSON 或 CSV 格式的项目权限白名单 |
| `SHOTGRID_READ_ONLY` | 否 | 设置为 `1` 时禁止 create/update/delete |
| `DCC_MCP_GATEWAY_PORT` | 否 | dcc-mcp 网关端口；设置为 `0` 表示仅独立运行 |
| `DCC_MCP_REGISTRY_DIR` | 否 | 共享网关 registry 目录 |
| `DCC_MCP_FPT_GATEWAY_SCENE` | 否 | 网关上下文标签；默认 `project:<SHOTGRID_PROJECT>` |
| `DCC_MCP_FPT_GATEWAY_DISPLAY_NAME` | 否 | 网关/管理界面展示的可读实例名称 |
| `DCC_MCP_FPT_ENABLE_GATEWAY_FAILOVER` | 否 | 设置为 `0` 时关闭 core 网关选举/故障转移 |
| `DCC_MCP_FPT_SKILL_PATHS` | 否 | FPT 专用 custom skill 搜索根目录（Windows 用 `;`，Unix 用 `:`） |
| `DCC_MCP_SKILL_PATHS` | 否 | 所有 dcc-mcp 适配器共享的全局 custom skill 搜索根目录 |
| `DCC_MCP_SHOTGRID_MINIMAL` | 否 | 逗号分隔的最小模式技能列表 |
| `DCC_MCP_SHOTGRID_DEFAULT_TOOLS` | 否 | 逗号分隔的默认激活工具 |

### 项目范围与权限

CRUD 和 batch 工具都支持可选的 `project`、`project_id` 和 `project_scoped`
输入。配置默认项目后，读操作会自动补 ShotGrid `project` 过滤条件，创建操作
会在缺少 `data.project` 时自动注入项目引用，更新和删除会在写入前校验实体所属
项目。

权限级别如下：

| 级别 | 允许操作 |
|------|----------|
| `read` | `find`、`find_one`、schema、连接检查 |
| `write` | `read` 加 create/update，以及不含 delete 的 batch |
| `admin` | `write` 加 delete/retire |

示例：

```bash
export SHOTGRID_PROJECT="my_project_code"
export SHOTGRID_PERMISSION_LEVEL="write"
export SHOTGRID_PROJECT_PERMISSIONS='{"my_project_code":"write","id:456":"read"}'
```

### 网关集成

该适配器使用与 Maya、Blender、Houdini、3ds Max 适配器一致的
`DccServerOptions.from_env(...)` 网关契约。设置 `DCC_MCP_GATEWAY_PORT` 或
`--gateway-port` 为正整数后，服务会发布 FPT 运行时条目，包含安全的展示名、
项目上下文标签、版本和网关选举诊断信息。

```bash
export SHOTGRID_PROJECT="my_project_code"
export DCC_MCP_GATEWAY_PORT=9765
export DCC_MCP_FPT_GATEWAY_DISPLAY_NAME="FPT my_project_code"

just serve-gateway
```

本地独立测试可使用 `--gateway-port 0` 或 `just serve-standalone`。
`shotgrid-discovery__get_server_info` 工具会返回 `gateway` 诊断对象，方便 agent
和 CI 确认当前实例是否已经加入网关。

### Agent 自动配置 Skill

`shotgrid-setup` 会在启动时加载，agent 可以直接用它生成本地配置，不需要猜项目
约定：

```bash
mcpcall call --url http://127.0.0.1:9765/mcp shotgrid-setup__validate_runtime_config
mcpcall call --url http://127.0.0.1:9765/mcp shotgrid-setup__generate_agent_config target=all
```

生成内容包含 `uvx dcc-mcp-fpt`、HTTP/stdio IDE 配置、mcpcall 命令、Docker
示例和 custom skill path 环境变量。默认会隐藏 secret 值。

### Custom Skills

将 `DCC_MCP_FPT_SKILL_PATHS` 指向某个 skill package 目录，或者指向包含多个
skill package 子目录的父目录：

```bash
# Windows 多个目录用分号。
set DCC_MCP_FPT_SKILL_PATHS=C:\studio\fpt-skills;C:\show\fpt-skills

# Linux/macOS 多个目录用冒号。
export DCC_MCP_FPT_SKILL_PATHS=/studio/fpt-skills:/show/fpt-skills

uvx dcc-mcp-fpt
```

跨适配器共享的 skills 使用 `DCC_MCP_SKILL_PATHS`。通过 gateway admin 添加的
skill path 也会在 dcc-mcp-core 启动或 reload 时被读取。

### 容器部署

本地构建并运行：

```bash
docker build -t dcc-mcp-fpt .
docker run --rm \
  -p 8765:8765 \
  -p 9765:9765 \
  --env-file .env \
  dcc-mcp-fpt
```

自定义 skills 可以挂载到 `/skills`；镜像默认设置了
`DCC_MCP_FPT_SKILL_PATHS=/skills`：

```bash
docker run --rm \
  -p 8765:8765 \
  -p 9765:9765 \
  --env-file .env \
  -v /studio/fpt-skills:/skills:ro \
  dcc-mcp-fpt
```

最小 compose：

```yaml
services:
  dcc-mcp-fpt:
    image: dcc-mcp-fpt
    ports:
      - "8765:8765"
      - "9765:9765"
    env_file:
      - .env
    volumes:
      - /studio/fpt-skills:/skills:ro
```

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

### 本地 Live CRUD Smoke

将 `.env.example` 复制为 `.env`，填入本地凭证，并保持该文件不提交。dry-run
命令只检查配置，默认跳过写入：

```bash
just install-dev
just live-crud-smoke-dry
```

要对配置项目执行真实的 create/find/update/delete，请确认该项目具备 admin 级别：

```bash
export SHOTGRID_PERMISSION_LEVEL="admin"
export SHOTGRID_LIVE_CRUD_CONFIRM=1
just live-crud-smoke
```

该 smoke 会创建临时实体、更新它，并在结束时 retire 清理。

## CI/CD

- `CI` 在 Linux、Windows、macOS 上覆盖 Python 3.8-3.12。
- lint、format check、技能元数据检查、CLI smoke、包构建和 Docker build 是独立 gate。
- `Release` 使用 release-please 管理版本，构建 wheel/sdist，通过 PyPI Trusted Publishing 发布，并把 dist 附加到 GitHub Release。
- `Live ShotGrid Smoke` 仅手动触发，读取 GitHub Secrets；默认 dry-run，只有确认后才执行真实 CRUD。

## 依赖

- Python 3.8+
- [dcc-mcp-core](https://github.com/dcc-mcp/dcc-mcp-core) >= 0.18.0
- [shotgun_api3](https://github.com/shotgunsoftware/python-api) >= 3.4.0

## 许可证

MIT — 详见 [LICENSE](LICENSE)。

## 相关项目

- [dcc-mcp-core](https://github.com/dcc-mcp/dcc-mcp-core) — 核心运行时和共享工具
- [shotgrid-mcp-server](https://github.com/loonghao/shotgrid-mcp-server) — 原始 FastMCP 实现
- [dcc-mcp-maya](https://github.com/dcc-mcp/dcc-mcp-maya) — Maya 适配器参考
- [dcc-mcp-blender](https://github.com/dcc-mcp/dcc-mcp-blender) — Blender 适配器参考
