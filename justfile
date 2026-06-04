set dotenv-load := true
set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]
set shell := ["bash", "-c"]

default:
    just --list

# Install development dependencies.
install-dev:
    python -m pip install --upgrade pip
    python -m pip install -e ".[dev]"

# Run unit tests with coverage.
test:
    python -m pytest tests/ --cov=src/dcc_mcp_fpt --cov-report=term

# Run unit tests with verbose output.
test-verbose:
    python -m pytest tests/ -vv --cov=src/dcc_mcp_fpt --cov-report=term

# Run ruff lint checks.
lint:
    python -m ruff check src/ tests/ tools/

# Validate bundled skill metadata.
lint-skills:
    python tools/lint_skills.py

# Format code.
format:
    python -m ruff format src/ tests/ tools/

# Check formatting without writing changes.
format-check:
    python -m ruff format --check src/ tests/ tools/

# Build package artifacts and verify metadata.
build:
    python -m pip install build twine
    python -m build
    python -m twine check dist/*

# Local CI gate used by GitHub Actions.
ci: lint format-check lint-skills test build

# Run the server locally in HTTP mode.
serve:
    python -m dcc_mcp_fpt http --host 0.0.0.0 --port 8765

# Run the server locally and join the dcc-mcp gateway.
serve-gateway:
    python -m dcc_mcp_fpt http --host 0.0.0.0 --port 8765

# Run the server locally with gateway registration disabled.
serve-standalone:
    python -m dcc_mcp_fpt http --host 0.0.0.0 --port 8765 --no-gateway

# Run the published package entry via uvx.
serve-uvx:
    uvx dcc-mcp-fpt

# Run the server in stdio mode.
serve-stdio:
    python -m dcc_mcp_fpt stdio

# Run a safe dry-run of the live ShotGrid smoke. Skips mutations.
live-crud-smoke-dry:
    python tools/shotgrid_live_crud_smoke.py

# Run live ShotGrid create/find/update/delete against the configured project.
live-crud-smoke:
    python tools/shotgrid_live_crud_smoke.py --confirm

# Build Docker image.
docker-build:
    docker build -t dcc-mcp-fpt .

# Run Docker container with ShotGrid env from the current shell or .env.
docker-run:
    docker run --rm -p 8765:8765 -p 9765:9765 -e SHOTGRID_URL -e SHOTGRID_SCRIPT_NAME -e SHOTGRID_SCRIPT_KEY -e SHOTGRID_PROJECT -e SHOTGRID_PROJECT_ID -e SHOTGRID_PERMISSION_LEVEL -e SHOTGRID_PROJECT_PERMISSIONS -e SHOTGRID_READ_ONLY -e DCC_MCP_GATEWAY_PORT -e DCC_MCP_REGISTRY_DIR -e DCC_MCP_FPT_GATEWAY_SCENE -e DCC_MCP_FPT_GATEWAY_DISPLAY_NAME -e DCC_MCP_FPT_ENABLE_GATEWAY_FAILOVER -e DCC_MCP_FPT_SKILL_PATHS -e DCC_MCP_SKILL_PATHS dcc-mcp-fpt

# Clean build and test artifacts.
clean:
    python -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in ('dist', 'build', '.pytest_cache', '.ruff_cache', 'htmlcov')]; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').glob('*.egg-info')]; [p.unlink(missing_ok=True) for p in pathlib.Path('.').glob('.coverage*')]"
