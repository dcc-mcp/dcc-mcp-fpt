"""dcc-mcp-fpt: ShotGrid (Flow Production Tracking) adapter for the DCC-MCP ecosystem.

Bridges AI assistants (Claude, Cursor, Copilot) to ShotGrid data through
typed MCP tools built on dcc-mcp-core.
"""

__version__ = "0.1.5"

from dcc_mcp_fpt.server import ShotGridMcpServer, start_server

__all__ = ["ShotGridMcpServer", "start_server", "__version__"]
