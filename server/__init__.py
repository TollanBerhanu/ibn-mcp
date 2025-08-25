"""
MCP Server implementations for the IBN MCP project.

This package contains various MCP server implementations including:
- Weather API server
- Demo server with basic tools
"""

from .weather import mcp as weather_mcp
from .server import mcp as demo_mcp

__all__ = ["weather_mcp", "demo_mcp"]
