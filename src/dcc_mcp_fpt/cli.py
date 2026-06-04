"""Command-line interface for dcc-mcp-fpt.

Supports stdio, HTTP, and ASGI transports.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Optional

from dcc_mcp_fpt.server import ShotGridMcpServer, start_server

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the CLI."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="dcc-mcp-fpt",
        description="ShotGrid (Flow Production Tracking) MCP server for the DCC-MCP ecosystem.",
    )

    # Transport mode
    parser.add_argument(
        "mode",
        nargs="?",
        default="http",
        choices=("http", "stdio", "asgi"),
        help="Transport mode (default: http)",
    )

    # HTTP options
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind HTTP server (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port for HTTP server (default: 8765)",
    )

    # ShotGrid connection
    parser.add_argument(
        "--shotgrid-url",
        default=os.environ.get("SHOTGRID_URL", ""),
        help="ShotGrid server URL. Defaults to SHOTGRID_URL env var.",
    )
    parser.add_argument(
        "--shotgrid-script-name",
        default=os.environ.get("SHOTGRID_SCRIPT_NAME", ""),
        help="ShotGrid script name. Defaults to SHOTGRID_SCRIPT_NAME env var.",
    )
    parser.add_argument(
        "--shotgrid-script-key",
        default=os.environ.get("SHOTGRID_SCRIPT_KEY", ""),
        help="ShotGrid script key. Defaults to SHOTGRID_SCRIPT_KEY env var.",
    )

    # Skills
    parser.add_argument(
        "--skills-dir",
        default=None,
        help="Path to custom skills directory.",
    )

    # General
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )

    return parser


def main(argv: Optional[list] = None) -> None:
    """Main CLI entry point."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    setup_logging(args.verbose)

    logger.info("Starting dcc-mcp-fpt (mode=%s, port=%d)", args.mode, args.port)

    try:
        if args.mode == "http":
            _run_http(args)
        elif args.mode == "stdio":
            _run_stdio(args)
        elif args.mode == "asgi":
            _run_asgi(args)
    except KeyboardInterrupt:
        logger.info("Server stopped by user.")
    except Exception as exc:
        logger.error("Server failed: %s", exc, exc_info=args.verbose)
        sys.exit(1)


def _run_http(args: argparse.Namespace) -> None:
    """Run in HTTP transport mode."""
    server = start_server(
        port=args.port,
        shotgrid_url=args.shotgrid_url or None,
        shotgrid_script_name=args.shotgrid_script_name or None,
        shotgrid_script_key=args.shotgrid_script_key or None,
    )
    url = server.mcp_url() if hasattr(server, "mcp_url") else f"http://{args.host}:{args.port}/mcp"
    logger.info("ShotGrid MCP server listening at %s", url)
    print(f"MCP endpoint: {url}")

    try:
        # Keep running until interrupted
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        logger.info("Server shut down.")


def _run_stdio(args: argparse.Namespace) -> None:
    """Run in stdio transport mode (for Claude Desktop, etc.)."""
    logger.info("Starting stdio transport — connect via stdin/stdout.")
    # dcc-mcp-core handles the stdio transport internally when configured
    server = ShotGridMcpServer(
        port=0,  # No HTTP port needed for stdio
        shotgrid_url=args.shotgrid_url or None,
        shotgrid_script_name=args.shotgrid_script_name or None,
        shotgrid_script_key=args.shotgrid_script_key or None,
    )
    # In stdio mode, the MCP protocol runs over stdin/stdout
    # The server handles the protocol internally
    try:
        server.start()
    except KeyboardInterrupt:
        server.shutdown()


def _run_asgi(args: argparse.Namespace) -> None:
    """Output ASGI application for use with uvicorn/gunicorn."""
    logger.info(
        "ASGI mode: run with 'uvicorn dcc_mcp_fpt.asgi:app --host %s --port %d'",
        args.host,
        args.port,
    )
    print(
        "Run with: uvicorn dcc_mcp_fpt.asgi:app "
        f"--host {args.host} --port {args.port}"
    )
