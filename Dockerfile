FROM python:3.11-slim

LABEL org.opencontainers.image.title="dcc-mcp-fpt"
LABEL org.opencontainers.image.description="ShotGrid MCP server for the DCC-MCP ecosystem"
LABEL org.opencontainers.image.source="https://github.com/dcc-mcp/dcc-mcp-fpt"

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Runtime env vars (override at container launch)
ENV SHOTGRID_URL=""
ENV SHOTGRID_SCRIPT_NAME=""
ENV SHOTGRID_SCRIPT_KEY=""
ENV DCC_MCP_SHOTGRID_PORT=8765

RUN pip install --no-cache-dir dcc-mcp-fpt

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8765/health')"

ENTRYPOINT ["dcc-mcp-fpt"]
CMD ["http", "--host", "0.0.0.0"]
