#!/usr/bin/env python3
"""
Demo script showing how to use the GNS3 MCP server

This script demonstrates the capabilities of the GNS3 MCP server
by showing example queries and expected responses.
"""

import asyncio
import sys
from client import MCPClient

async def demo_gns3_server():
    """Demonstrate the GNS3 MCP server capabilities"""
    
    print("=== GNS3 MCP Server Demo ===\n")
    
    # Initialize client
    client = MCPClient()
    
    try:
        # Connect to the GNS3 server
        await client.connect_to_server("server/gns3_mcp.py")
        
        print("Connected to GNS3 MCP Server!")
        print("Available tools:", [tool.name for tool in (await client.session.list_tools()).tools])
        print("\n" + "="*50 + "\n")
        
        # Example queries that users can ask
        example_queries = [
            "Connect to my GNS3 server at http://localhost:3080",
            "List all available projects on the server",
            "Show me all available templates",
            "Create a simple topology with 2 firewalls and 4 workstations in project 'My Network'",
            "Start all nodes in project 'My Network'",
            "Create a custom topology with a DMZ network containing 2 firewalls, 3 web servers, and a load balancer"
        ]
        
        print("Example natural language queries you can ask:")
        for i, query in enumerate(example_queries, 1):
            print(f"{i}. {query}")
        
        print("\n" + "="*50)
        print("The GNS3 MCP server provides these capabilities:")
        print("\n1. **Server Management**:")
        print("   - Connect to GNS3 servers with authentication")
        print("   - List available projects and templates")
        
        print("\n2. **Topology Creation**:")
        print("   - Create simple topologies with predefined layouts")
        print("   - Create custom topologies from natural language descriptions")
        print("   - Automatic node placement and linking")
        
        print("\n3. **Node Management**:")
        print("   - Start and stop all nodes in a project")
        print("   - Monitor node status")
        
        print("\n4. **Natural Language Interface**:")
        print("   - Describe topologies in plain English")
        print("   - AI-powered topology interpretation")
        print("   - Automatic template selection and configuration")
        
        print("\n" + "="*50)
        print("To use the GNS3 server:")
        print("1. Run: uv run mcp-server gns3")
        print("2. In another terminal: uv run mcp-client server/gns3_mcp.py")
        print("3. Ask questions like the examples above!")
        
    except Exception as e:
        print(f"Error in demo: {e}")
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(demo_gns3_server())
