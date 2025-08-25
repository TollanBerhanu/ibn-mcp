"""
Main entry point for MCP servers.

This module provides a unified interface to run different MCP servers.
"""

import sys
from .weather import main as weather_main
from .server import main as demo_main


def main():
    """Main entry point for MCP servers"""
    if len(sys.argv) < 2:
        print("Usage: mcp-server <server_type>")
        print("Available server types:")
        print("  weather - Weather API server with forecast and alerts")
        print("  demo    - Demo server with basic tools")
        sys.exit(1)
    
    server_type = sys.argv[1].lower()
    
    if server_type == "weather":
        weather_main()
    elif server_type == "demo":
        demo_main()
    else:
        print(f"Unknown server type: {server_type}")
        print("Available server types: weather, demo")
        sys.exit(1)


if __name__ == "__main__":
    main()
