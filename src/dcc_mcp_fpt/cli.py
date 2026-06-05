"""Command-line interface for dcc-mcp-fpt.

Supports stdio, HTTP, and ASGI transports.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading
from pathlib import Path
from typing import Optional

from dcc_mcp_fpt.server import ShotGridMcpServer, start_server

logger = logging.getLogger(__name__)
DEFAULT_GATEWAY_PORT = 9765


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

    # Gateway options
    parser.add_argument(
        "--gateway-port",
        type=int,
        default=_env_int("DCC_MCP_GATEWAY_PORT", DEFAULT_GATEWAY_PORT),
        help="dcc-mcp gateway port. Defaults to DCC_MCP_GATEWAY_PORT or 9765; use 0 to disable.",
    )
    parser.add_argument(
        "--no-gateway",
        action="store_true",
        help="Disable gateway registration and run only the adapter endpoint.",
    )
    parser.add_argument(
        "--registry-dir",
        default=os.environ.get("DCC_MCP_REGISTRY_DIR", ""),
        help="Gateway registry directory. Defaults to DCC_MCP_REGISTRY_DIR.",
    )
    parser.add_argument(
        "--gateway-scene",
        default=os.environ.get("DCC_MCP_FPT_GATEWAY_SCENE", ""),
        help="Gateway context label. Defaults to the configured ShotGrid project.",
    )
    parser.add_argument(
        "--gateway-display-name",
        default=os.environ.get("DCC_MCP_FPT_GATEWAY_DISPLAY_NAME", ""),
        help="Human-readable FPT instance label shown in gateway/admin surfaces.",
    )
    parser.add_argument(
        "--disable-gateway-failover",
        action="store_true",
        help="Disable core gateway election/failover for this FPT server.",
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
    parser.add_argument(
        "--shotgrid-project",
        default=os.environ.get("SHOTGRID_PROJECT", os.environ.get("SHOTGRID_DEFAULT_PROJECT", "")),
        help="Default ShotGrid project name, code, or tank name for scoped CRUD tools.",
    )
    parser.add_argument(
        "--shotgrid-project-id",
        type=int,
        default=_env_int("SHOTGRID_PROJECT_ID"),
        help="Default ShotGrid project ID for scoped CRUD tools.",
    )
    parser.add_argument(
        "--shotgrid-permission-level",
        choices=("read", "write", "admin"),
        default=os.environ.get("SHOTGRID_PERMISSION_LEVEL", ""),
        help="Fallback permission level for the default project.",
    )

    # Skills
    parser.add_argument(
        "--skills-dir",
        default=None,
        help="Path to an alternate bundled skills directory for adapter development.",
    )
    parser.add_argument(
        "--skill-path",
        action="append",
        default=[],
        help=("Additional custom skill search root. Repeatable. Merged into DCC_MCP_FPT_SKILL_PATHS before startup."),
    )

    # General
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )

    return parser


def main(argv: Optional[list] = None) -> None:
    """Main CLI entry point."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.shotgrid_permission_level:
        os.environ["SHOTGRID_PERMISSION_LEVEL"] = args.shotgrid_permission_level
    args.gateway_port = _normalize_gateway_port(args)
    _apply_skill_paths(args.skill_path)

    setup_logging(args.verbose)

    logger.info(
        "Starting dcc-mcp-fpt (mode=%s, port=%d, gateway_port=%s)",
        args.mode,
        args.port,
        args.gateway_port,
    )

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
        shotgrid_project=args.shotgrid_project or None,
        shotgrid_project_id=args.shotgrid_project_id,
        gateway_port=args.gateway_port,
        registry_dir=args.registry_dir or None,
        gateway_scene=args.gateway_scene or None,
        gateway_display_name=args.gateway_display_name or None,
        enable_gateway_failover=False if args.disable_gateway_failover else None,
        skills_dir=Path(args.skills_dir) if args.skills_dir else None,
    )
    url = server.mcp_url() if hasattr(server, "mcp_url") else f"http://{args.host}:{args.port}/mcp"
    logger.info("ShotGrid MCP server listening at %s", url)
    print(f"MCP endpoint: {url}")
    if args.gateway_port and args.gateway_port > 0:
        print(f"Gateway endpoint: http://127.0.0.1:{args.gateway_port}/mcp")

    shutdown_event = threading.Event()

    def _handle_shutdown(signum, frame):
        signame = signal.Signals(signum).name if hasattr(signal, "Signals") else f"signal {signum}"
        logger.info("Received %s, initiating graceful shutdown...", signame)
        shutdown_event.set()

    for sig in _graceful_signals():
        try:
            signal.signal(sig, _handle_shutdown)
        except (ValueError, AttributeError):
            pass  # Signal not available on this platform

    try:
        while not shutdown_event.is_set():
            shutdown_event.wait(timeout=1.0)
    finally:
        server.shutdown()
        logger.info("Server shut down gracefully.")


def _run_stdio(args: argparse.Namespace) -> None:
    """Run in stdio transport mode (for Claude Desktop, etc.)."""
    logger.info("Starting stdio transport — connect via stdin/stdout.")
    # dcc-mcp-core handles the stdio transport internally when configured
    server = ShotGridMcpServer(
        port=0,  # No HTTP port needed for stdio
        shotgrid_url=args.shotgrid_url or None,
        shotgrid_script_name=args.shotgrid_script_name or None,
        shotgrid_script_key=args.shotgrid_script_key or None,
        shotgrid_project=args.shotgrid_project or None,
        shotgrid_project_id=args.shotgrid_project_id,
        gateway_port=args.gateway_port,
        registry_dir=args.registry_dir or None,
        gateway_scene=args.gateway_scene or None,
        gateway_display_name=args.gateway_display_name or None,
        enable_gateway_failover=False if args.disable_gateway_failover else None,
        skills_dir=Path(args.skills_dir) if args.skills_dir else None,
    )
    # In stdio mode, the MCP protocol runs over stdin/stdout
    # The server handles the protocol internally
    shutdown_event = threading.Event()

    def _handle_shutdown(signum, frame):
        signame = signal.Signals(signum).name if hasattr(signal, "Signals") else f"signal {signum}"
        logger.info("Received %s, initiating graceful shutdown...", signame)
        shutdown_event.set()

    for sig in _graceful_signals():
        try:
            signal.signal(sig, _handle_shutdown)
        except (ValueError, AttributeError):
            pass

    try:
        server.start()
        # In stdio mode, start() typically blocks on stdin/stdout I/O.
        # The shutdown_event allows SIGTERM to trigger a clean exit path
        # when the platform sends signals during orchestrated shutdown.
        while not shutdown_event.is_set():
            shutdown_event.wait(timeout=1.0)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        logger.info("Server shut down gracefully.")


def _run_asgi(args: argparse.Namespace) -> None:
    """Output ASGI application for use with uvicorn/gunicorn."""
    logger.info(
        "ASGI mode: run with 'uvicorn dcc_mcp_fpt.asgi:app --host %s --port %d'",
        args.host,
        args.port,
    )
    print(f"Run with: uvicorn dcc_mcp_fpt.asgi:app --host {args.host} --port {args.port}")


def _env_int(name: str, default: Optional[int] = None) -> Optional[int]:
    value = os.environ.get(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _normalize_gateway_port(args: argparse.Namespace) -> Optional[int]:
    """Resolve CLI gateway switches to the final port value."""
    if getattr(args, "no_gateway", False):
        return 0
    return args.gateway_port


def _graceful_signals():
    """Return the platform-appropriate graceful-shutdown signals.

    On Unix: SIGTERM (orchestrator stop) and SIGINT (Ctrl+C).
    On Windows: SIGINT and SIGBREAK when available, otherwise just SIGINT.
    """
    sigs = []
    for name in ("SIGTERM", "SIGINT", "SIGBREAK"):
        sig = getattr(signal, name, None)
        if sig is not None:
            sigs.append(sig)
    return sigs


def _apply_skill_paths(skill_paths: list[str]) -> None:
    """Merge repeatable --skill-path values into DCC_MCP_FPT_SKILL_PATHS."""
    cleaned = [path for path in skill_paths if path]
    if not cleaned:
        return

    existing = os.environ.get("DCC_MCP_FPT_SKILL_PATHS", "")
    parts = [part for part in existing.split(os.pathsep) if part] if existing else []
    for path in cleaned:
        if path not in parts:
            parts.append(path)
    os.environ["DCC_MCP_FPT_SKILL_PATHS"] = os.pathsep.join(parts)
