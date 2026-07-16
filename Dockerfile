FROM python:3.11-slim

LABEL org.opencontainers.image.title="dcc-mcp-fpt"
LABEL org.opencontainers.image.description="ShotGrid MCP server for the DCC-MCP ecosystem"
LABEL org.opencontainers.image.source="https://github.com/dcc-mcp/dcc-mcp-fpt"

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# Runtime env vars (override at container launch)
ENV SHOTGRID_URL=""
ENV SHOTGRID_SCRIPT_NAME=""
ENV SHOTGRID_SCRIPT_KEY=""
ENV SHOTGRID_PROJECT=""
ENV SHOTGRID_PROJECT_ID=""
ENV SHOTGRID_PERMISSION_LEVEL="read"
ENV DCC_MCP_GATEWAY_PORT=9765
ENV DCC_MCP_REGISTRY_DIR=""
ENV DCC_MCP_FPT_GATEWAY_SCENE=""
ENV DCC_MCP_FPT_GATEWAY_DISPLAY_NAME=""
ENV DCC_MCP_FPT_ENABLE_GATEWAY_FAILOVER=1
ENV DCC_MCP_FPT_SKILL_PATHS="/skills"
ENV DCC_MCP_SKILL_PATHS=""

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN mkdir -p /skills && pip install --no-cache-dir .

EXPOSE 9765
VOLUME ["/skills"]
STOPSIGNAL SIGTERM

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9765/health')"

ENTRYPOINT ["dcc-mcp-fpt"]
CMD ["http", "--host", "0.0.0.0"]
