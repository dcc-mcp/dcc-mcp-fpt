# Run tests
test:
    uv pip install --system -e ".[dev]"
    ruff check src/ tests/
    pytest --cov=src/dcc_mcp_fpt --cov-report=term

# Run tests with verbose output
test-verbose:
    uv pip install --system -e ".[dev]"
    pytest -vv --cov=src/dcc_mcp_fpt --cov-report=term

# Lint only
lint:
    ruff check src/ tests/

# Format code
format:
    ruff format src/ tests/

# Build package
build:
    uv pip install --system hatchling build
    python -m build

# Clean build artifacts
clean:
    rm -rf dist build *.egg-info .pytest_cache .ruff_cache

# Run the server locally (HTTP mode)
serve:
    uv run dcc-mcp-fpt http --host 0.0.0.0 --port 8765

# Run the server in stdio mode (for Claude Desktop)
serve-stdio:
    uv run dcc-mcp-fpt stdio

# Build Docker image
docker-build:
    docker build -t dcc-mcp-fpt .

# Run Docker container
docker-run:
    docker run --rm -p 8765:8765 \
        -e SHOTGRID_URL=${SHOTGRID_URL} \
        -e SHOTGRID_SCRIPT_NAME=${SHOTGRID_SCRIPT_NAME} \
        -e SHOTGRID_SCRIPT_KEY=${SHOTGRID_SCRIPT_KEY} \
        dcc-mcp-fpt
