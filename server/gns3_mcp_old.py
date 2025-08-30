# """
# GNS3 MCP Server

# This MCP server provides tools for creating and managing network topologies in GNS3
# using natural language commands. It wraps the GNS3 API to allow users to describe
# network topologies in plain English.
# """

# import os
# import time
# import requests
# from typing import Any, Dict, List, Optional
# from mcp.server.fastmcp import FastMCP

# # Initialize FastMCP server
# mcp = FastMCP("gns3")

# # Global session for GNS3 API calls
# gns3_session = requests.Session()
# gns3_session.headers.update({
#     "Accept": "application/json", 
#     "Content-Type": "application/json"
# })

# # Default GNS3 server from environment variable
# DEFAULT_GNS3_SERVER = os.getenv("GNS3_SERVER", "http://172.16.194.129:80")

# def gns3_get(url: str) -> Dict[str, Any]:
#     """Make a GET request to GNS3 API"""
#     r = gns3_session.get(url)
#     r.raise_for_status()
#     return r.json()

# def gns3_post(url: str, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
#     """Make a POST request to GNS3 API"""
#     r = gns3_session.post(url, json=json_data or {})
#     r.raise_for_status()
#     return r.json() if r.text else {}

# def find_project_id(base_url: str, project_name: str) -> str:
#     """Find project ID by name"""
#     projects = gns3_get(f"{base_url}/v2/projects")
#     for p in projects:
#         if p.get("name") == project_name:
#             return p["project_id"]
#     raise ValueError(f"Project named '{project_name}' not found")

# def get_template_map(base_url: str) -> Dict[str, str]:
#     """Get mapping of template names to IDs"""
#     templates = gns3_get(f"{base_url}/v2/templates")
#     return {t.get("name"): t.get("template_id") for t in templates}

# def add_node_from_template(base_url: str, project_id: str, template_id: str, name: str, x: int, y: int) -> Dict[str, Any]:
#     """Add a node from template"""
#     url = f"{base_url}/v2/projects/{project_id}/templates/{template_id}"
#     payload = {"compute_id": "local", "x": x, "y": y, "name": name}
#     return gns3_post(url, json=payload)

# def link_nodes(base_url: str, project_id: str, node1_id: str, node2_id: str, 
#                node1_adapter: int = 0, node1_port: int = 0,
#                node2_adapter: int = 0, node2_port: int = 0) -> Dict[str, Any]:
#     """Link two nodes together"""
#     url = f"{base_url}/v2/projects/{project_id}/links"
#     payload = {
#         "nodes": [
#             {"node_id": node1_id, "adapter_number": node1_adapter, "port_number": node1_port},
#             {"node_id": node2_id, "adapter_number": node2_adapter, "port_number": node2_port},
#         ]
#     }
#     return gns3_post(url, json=payload)

# def start_node(base_url: str, project_id: str, node_id: str) -> bool:
#     """Start a node"""
#     url = f"{base_url}/v2/projects/{project_id}/nodes/{node_id}/start"
#     try:
#         gns3_post(url)
#         return True
#     except requests.HTTPError:
#         # Some nodes may auto-start or not support /start
#         return False

# @mcp.tool()
# async def connect_to_gns3(server_url: Optional[str] = None, 
#                           username: Optional[str] = None, 
#                           password: Optional[str] = None) -> str:
#     """Connect to a GNS3 server and configure authentication.
#     WARNING: Do NOT use this tool for creating topologies!
#     Use this tool ONLY when you need to test connectivity or configure authentication.
#     For creating topologies, use create_simple_topology, create_vpcs_topology, or create_vpcs_network directly.
    
#     Args:
#         server_url: GNS3 server URL (defaults to GNS3_SERVER environment variable or http://172.16.194.129:80)
#         username: Basic auth username (optional)
#         password: Basic auth password (optional)
#     """
#     global gns3_session
    
#     # Use provided server URL or default from environment
#     if not server_url:
#         server_url = DEFAULT_GNS3_SERVER
    
#     # Configure authentication if provided
#     if username and password:
#         gns3_session.auth = (username, password)
    
#     # Test connection
#     try:
#         projects = gns3_get(f"{server_url.rstrip('/')}/v2/projects")
#         return f"✅ Successfully connected to GNS3 server at {server_url}. Found {len(projects)} projects.\n\n" \
#                f"💡 For creating topologies, use these tools directly:\n" \
#                f"- 'create_simple_topology' for firewalls/workstations\n" \
#                f"- 'create_vpcs_topology' for VPCS networks\n" \
#                f"- 'create_vpcs_network' for VPCS networks (simplified)\n" \
#                f"- 'list_projects' to see available projects\n" \
#                f"- 'list_templates' to see available node templates"
#     except Exception as e:
#         return f"❌ Failed to connect to GNS3 server: {str(e)}"

# @mcp.tool()
# async def list_projects(server_url: Optional[str] = None) -> str:
#     """List all available projects on the GNS3 server.
    
#     Args:
#         server_url: GNS3 server URL (defaults to GNS3_SERVER environment variable)
#     """
#     if not server_url:
#         server_url = DEFAULT_GNS3_SERVER
        
#     try:
#         projects = gns3_get(f"{server_url.rstrip('/')}/v2/projects")
#         if not projects:
#             return "No projects found on the server."
        
#         project_list = []
#         for p in projects:
#             project_list.append(f"- {p.get('name', 'Unknown')} (ID: {p.get('project_id', 'Unknown')})")
        
#         return f"📁 Available projects:\n" + "\n".join(project_list) + \
#                f"\n\n💡 Use 'create_simple_topology' with one of these project names to create a network!"
#     except Exception as e:
#         return f"❌ Error listing projects: {str(e)}"

# @mcp.tool()
# async def list_templates(server_url: Optional[str] = None) -> str:
#     """List all available templates on the GNS3 server.
    
#     Args:
#         server_url: GNS3 server URL (defaults to GNS3_SERVER environment variable)
#     """
#     if not server_url:
#         server_url = DEFAULT_GNS3_SERVER
        
#     try:
#         templates = gns3_get(f"{server_url.rstrip('/')}/v2/templates")
#         if not templates:
#             return "No templates found on the server."
        
#         template_list = []
#         for t in templates:
#             template_list.append(f"- {t.get('name', 'Unknown')} (ID: {t.get('template_id', 'Unknown')})")
        
#         return f"🔧 Available templates:\n" + "\n".join(template_list) + \
#                f"\n\n💡 Use 'create_simple_topology' with template names to create a network!"
#     except Exception as e:
#         return f"❌ Error listing templates: {str(e)}"

# @mcp.tool()
# async def create_simple_topology(project_name: str,
#                                 firewalls: int = 0,
#                                 workstations: int = 0,
#                                 firewall_template: str = "Firewall Docker",
#                                 workstation_template: str = "Workstation Docker",
#                                 switch_template: str = "Ethernet switch",
#                                 server_url: Optional[str] = None,
#                                 start_x: int = 100,
#                                 start_y: int = 100,
#                                 x_spacing: int = 180,
#                                 y_spacing: int = 130,
#                                 devices_per_row: int = 6,
#                                 custom_nodes: Optional[str] = None,
#                                 custom_node_template: Optional[str] = None,
#                                 custom_node_count: int = 0) -> str:
#     """Create a complete network topology with various node types and a switch.
#     This tool handles the entire workflow: connection, node creation, linking, and starting.
#     No need to call connect_to_gns3 first - this tool handles everything automatically.
    
#     Args:
#         project_name: Name of the existing GNS3 project
#         firewalls: Number of firewall nodes to create
#         workstations: Number of workstation nodes to create
#         firewall_template: Template name for firewall nodes
#         workstation_template: Template name for workstation nodes
#         switch_template: Template name for the switch
#         server_url: GNS3 server URL (defaults to GNS3_SERVER environment variable)
#         start_x: Starting X coordinate for layout
#         start_y: Starting Y coordinate for layout
#         x_spacing: Horizontal spacing between nodes
#         y_spacing: Vertical spacing between rows
#         devices_per_row: Maximum devices per row in the layout
#         custom_nodes: Name prefix for custom nodes (e.g., "VPCS", "Router")
#         custom_node_template: Template name for custom nodes
#         custom_node_count: Number of custom nodes to create
#     """
#     if not server_url:
#         server_url = DEFAULT_GNS3_SERVER
        
#     try:
#         base_url = server_url.rstrip('/')
        
#         # Step 1: Find project
#         project_id = find_project_id(base_url, project_name)
        
#         # Step 2: Get templates
#         template_map = get_template_map(base_url)
#         fw_tid = template_map.get(firewall_template)
#         ws_tid = template_map.get(workstation_template)
#         sw_tid = template_map.get(switch_template)
        
#         if not fw_tid:
#             return f"❌ Firewall template '{firewall_template}' not found.\nAvailable templates: {', '.join(sorted(template_map.keys()))}"
#         if not ws_tid:
#             return f"❌ Workstation template '{workstation_template}' not found.\nAvailable templates: {', '.join(sorted(template_map.keys()))}"
#         if not sw_tid:
#             return f"❌ Switch template '{switch_template}' not found.\nAvailable templates: {', '.join(sorted(template_map.keys()))}"
        
#         # Step 3: Create switch
#         switch_x = start_x + (x_spacing * min(devices_per_row, firewalls + workstations)) // 2
#         switch_y = start_y
#         switch_node = add_node_from_template(base_url, project_id, sw_tid, "Core-Switch", switch_x, switch_y)
#         switch_id = switch_node["node_id"]
        
#         # Step 4: Create nodes
#         created_nodes = []
#         current_index = 0
        
#         def grid_pos(idx):
#             row = idx // devices_per_row
#             col = idx % devices_per_row
#             x = start_x + col * x_spacing
#             y = start_y + y_spacing * (row + 1)
#             return x, y
        
#         # Create firewalls
#         for i in range(firewalls):
#             name = f"FW-{i+1}"
#             x, y = grid_pos(current_index)
#             node = add_node_from_template(base_url, project_id, fw_tid, name, x, y)
#             created_nodes.append((node["node_id"], name))
#             current_index += 1
        
#         # Create workstations
#         for i in range(workstations):
#             name = f"WS-{i+1}"
#             x, y = grid_pos(current_index)
#             node = add_node_from_template(base_url, project_id, ws_tid, name, x, y)
#             created_nodes.append((node["node_id"], name))
#             current_index += 1
        
#         # Create custom nodes (e.g., VPCS, Routers, etc.)
#         if custom_nodes and custom_node_template and custom_node_count > 0:
#             custom_tid = template_map.get(custom_node_template)
#             if not custom_tid:
#                 return f"❌ Custom node template '{custom_node_template}' not found.\nAvailable templates: {', '.join(sorted(template_map.keys()))}"
            
#             for i in range(custom_node_count):
#                 name = f"{custom_nodes}-{i+1}"
#                 x, y = grid_pos(current_index)
#                 node = add_node_from_template(base_url, project_id, custom_tid, name, x, y)
#                 created_nodes.append((node["node_id"], name))
#                 current_index += 1
        
#         # Step 5: Link all devices to switch
#         switch_port = 0
#         for node_id, name in created_nodes:
#             link = link_nodes(base_url, project_id, switch_id, node_id, switch_port=switch_port)
#             switch_port += 1
#             time.sleep(0.05)  # Small delay to avoid overwhelming server
        
#         # Step 6: Start nodes
#         started = 0
#         for node_id, name in created_nodes + [(switch_id, "Core-Switch")]:
#             if start_node(base_url, project_id, node_id):
#                 started += 1
        
#         # Build summary message
#         summary_parts = []
#         if firewalls > 0:
#             summary_parts.append(f"{firewalls} firewalls")
#         if workstations > 0:
#             summary_parts.append(f"{workstations} workstations")
#         if custom_nodes and custom_node_count > 0:
#             summary_parts.append(f"{custom_node_count} {custom_nodes}")
        
#         summary = ", ".join(summary_parts) if summary_parts else "0 devices"
        
#         return f"🎉 Successfully created complete topology in project '{project_name}':\n\n" \
#                f"✅ Created {len(created_nodes)} devices ({summary})\n" \
#                f"✅ Created 1 switch\n" \
#                f"✅ Linked all devices to the switch\n" \
#                f"✅ Started {started} nodes\n\n" \
#                f"🌐 Your network is now ready! Open GNS3 to see the topology."
               
#     except Exception as e:
#         return f"❌ Error creating topology: {str(e)}"

# @mcp.tool()
# async def create_vpcs_topology(project_name: str,
#                               vpcs_count: int = 2,
#                               vpcs_template: str = "VPCS",
#                               switch_template: str = "Ethernet switch",
#                               server_url: Optional[str] = None) -> str:
#     """Create a simple topology with VPCS nodes connected to a switch.
#     IMPORTANT: This tool handles EVERYTHING automatically - connection, node creation, linking, and starting.
#     DO NOT call connect_to_gns3 first. Use this tool directly for VPCS networks.
    
#     Args:
#         project_name: Name of the existing GNS3 project
#         vpcs_count: Number of VPCS nodes to create
#         vpcs_template: Template name for VPCS nodes (default: "VPCS")
#         switch_template: Template name for the switch (default: "Ethernet switch")
#         server_url: GNS3 server URL (defaults to GNS3_SERVER environment variable)
#     """
#     if not server_url:
#         server_url = DEFAULT_GNS3_SERVER
        
#     try:
#         base_url = server_url.rstrip('/')
        
#         # Step 1: Find project
#         project_id = find_project_id(base_url, project_name)
        
#         # Step 2: Get templates
#         template_map = get_template_map(base_url)
#         vpcs_tid = template_map.get(vpcs_template)
#         sw_tid = template_map.get(switch_template)
        
#         if not vpcs_tid:
#             return f"❌ VPCS template '{vpcs_template}' not found.\nAvailable templates: {', '.join(sorted(template_map.keys()))}"
#         if not sw_tid:
#             return f"❌ Switch template '{switch_template}' not found.\nAvailable templates: {', '.join(sorted(template_map.keys()))}"
        
#         # Step 3: Create switch
#         switch_x = 300
#         switch_y = 100
#         switch_node = add_node_from_template(base_url, project_id, sw_tid, "Core-Switch", switch_x, switch_y)
#         switch_id = switch_node["node_id"]
        
#         # Step 4: Create VPCS nodes
#         created_nodes = []
#         for i in range(vpcs_count):
#             name = f"VPCS-{i+1}"
#             x = 100 + (i * 200)  # Spread them horizontally
#             y = 250
#             node = add_node_from_template(base_url, project_id, vpcs_tid, name, x, y)
#             created_nodes.append((node["node_id"], name))
        
#         # Step 5: Link all VPCS to switch
#         switch_port = 0
#         for node_id, name in created_nodes:
#             link = link_nodes(base_url, project_id, switch_id, node_id, switch_port=switch_port)
#             switch_port += 1
#             time.sleep(0.05)
        
#         # Step 6: Start nodes
#         started = 0
#         for node_id, name in created_nodes + [(switch_id, "Core-Switch")]:
#             if start_node(base_url, project_id, node_id):
#                 started += 1
        
#         return f"🎉 Successfully created VPCS topology in project '{project_name}':\n\n" \
#                f"✅ Created {len(created_nodes)} VPCS nodes\n" \
#                f"✅ Created 1 switch\n" \
#                f"✅ Linked all VPCS nodes to the switch\n" \
#                f"✅ Started {started} nodes\n\n" \
#                f"🌐 Your VPCS network is now ready! Open GNS3 to see the topology."
               
#     except Exception as e:
#         return f"❌ Error creating VPCS topology: {str(e)}"

# @mcp.tool()
# async def create_custom_topology(project_name: str,
#                                 topology_description: str,
#                                 server_url: Optional[str] = None) -> str:
#     """Create a custom topology based on a natural language description.
#     This tool provides guidance for creating complex topologies.
    
#     Args:
#         project_name: Name of the existing GNS3 project
#         topology_description: Natural language description of the topology to create
#         server_url: GNS3 server URL (defaults to GNS3_SERVER environment variable)
#     """
#     if not server_url:
#         server_url = DEFAULT_GNS3_SERVER
        
#     try:
#         base_url = server_url.rstrip('/')
        
#         # Find project
#         project_id = find_project_id(base_url, project_name)
        
#         # Get available templates
#         template_map = get_template_map(base_url)
#         available_templates = list(template_map.keys())
        
#         return f"🎯 Custom topology request: '{topology_description}'\n\n" \
#                f"📋 Available templates for your topology:\n" + \
#                "\n".join([f"- {template}" for template in available_templates]) + \
#                f"\n\n💡 Use these specialized tools:\n" \
#                f"• 'create_simple_topology' for firewalls/workstations\n" \
#                f"• 'create_vpcs_topology' for VPCS networks\n" \
#                f"• Or use 'create_simple_topology' with custom_node_template parameter"
               
#     except Exception as e:
#         return f"❌ Error creating custom topology: {str(e)}"

# @mcp.tool()
# async def create_vpcs_network(project_name: str,
#                              vpcs_count: int = 2,
#                              server_url: Optional[str] = None) -> str:
#     """Create a VPCS network with the specified number of VPCS nodes connected to a switch.
#     This tool is specifically designed for VPCS networks and handles everything automatically.
#     Use this tool directly - no need to call connect_to_gns3 first.
    
#     Args:
#         project_name: Name of the existing GNS3 project
#         vpcs_count: Number of VPCS nodes to create (default: 2)
#         server_url: GNS3 server URL (defaults to GNS3_SERVER environment variable)
#     """
#     if not server_url:
#         server_url = DEFAULT_GNS3_SERVER
        
#     try:
#         base_url = server_url.rstrip('/')
        
#         # Step 1: Find project
#         project_id = find_project_id(base_url, project_name)
        
#         # Step 2: Get templates
#         template_map = get_template_map(base_url)
#         vpcs_tid = template_map.get("VPCS")
#         sw_tid = template_map.get("Ethernet switch")
        
#         if not vpcs_tid:
#             return f"❌ VPCS template not found.\nAvailable templates: {', '.join(sorted(template_map.keys()))}"
#         if not sw_tid:
#             return f"❌ Ethernet switch template not found.\nAvailable templates: {', '.join(sorted(template_map.keys()))}"
        
#         # Step 3: Create switch
#         switch_x = 300
#         switch_y = 100
#         switch_node = add_node_from_template(base_url, project_id, sw_tid, "Core-Switch", switch_x, switch_y)
#         switch_id = switch_node["node_id"]
        
#         # Step 4: Create VPCS nodes
#         created_nodes = []
#         for i in range(vpcs_count):
#             name = f"VPCS-{i+1}"
#             x = 100 + (i * 200)  # Spread them horizontally
#             y = 250
#             node = add_node_from_template(base_url, project_id, vpcs_tid, name, x, y)
#             created_nodes.append((node["node_id"], name))
        
#         # Step 5: Link all VPCS to switch
#         switch_port = 0
#         for node_id, name in created_nodes:
#             link = link_nodes(base_url, project_id, switch_id, node_id, switch_port=switch_port)
#             switch_port += 1
#             time.sleep(0.05)
        
#         # Step 6: Start nodes
#         started = 0
#         for node_id, name in created_nodes + [(switch_id, "Core-Switch")]:
#             if start_node(base_url, project_id, node_id):
#                 started += 1
        
#         return f"🎉 Successfully created VPCS network in project '{project_name}':\n\n" \
#                f"✅ Created {len(created_nodes)} VPCS nodes\n" \
#                f"✅ Created 1 Ethernet switch\n" \
#                f"✅ Linked all VPCS nodes to the switch\n" \
#                f"✅ Started {started} nodes\n\n" \
#                f"🌐 Your VPCS network is now ready! Open GNS3 to see the topology."
               
#     except Exception as e:
#         return f"❌ Error creating VPCS network: {str(e)}"

# @mcp.tool()
# async def start_project_nodes(project_name: str,
#                              server_url: Optional[str] = None) -> str:
#     """Start all nodes in a project.
    
#     Args:
#         project_name: Name of the GNS3 project
#         server_url: GNS3 server URL (defaults to GNS3_SERVER environment variable)
#     """
#     if not server_url:
#         server_url = DEFAULT_GNS3_SERVER
        
#     try:
#         base_url = server_url.rstrip('/')
#         project_id = find_project_id(base_url, project_name)
        
#         # Get all nodes in the project
#         nodes = gns3_get(f"{base_url}/v2/projects/{project_id}/nodes")
        
#         started_count = 0
#         for node in nodes:
#             node_id = node["node_id"]
#             node_name = node.get("name", "Unknown")
#             if start_node(base_url, project_id, node_id):
#                 started_count += 1
        
#         return f"🚀 Started {started_count} out of {len(nodes)} nodes in project '{project_name}'"
        
#     except Exception as e:
#         return f"❌ Error starting nodes: {str(e)}"

# @mcp.tool()
# async def stop_project_nodes(project_name: str,
#                             server_url: Optional[str] = None) -> str:
#     """Stop all nodes in a project.
    
#     Args:
#         project_name: Name of the GNS3 project
#         server_url: GNS3 server URL (defaults to GNS3_SERVER environment variable)
#     """
#     if not server_url:
#         server_url = DEFAULT_GNS3_SERVER
        
#     try:
#         base_url = server_url.rstrip('/')
#         project_id = find_project_id(base_url, project_name)
        
#         # Get all nodes in the project
#         nodes = gns3_get(f"{base_url}/v2/projects/{project_id}/nodes")
        
#         stopped_count = 0
#         for node in nodes:
#             node_id = node["node_id"]
#             node_name = node.get("name", "Unknown")
#             try:
#                 url = f"{base_url}/v2/projects/{project_id}/nodes/{node_id}/stop"
#                 gns3_post(url)
#                 stopped_count += 1
#             except requests.HTTPError:
#                 # Some nodes may not support stop or already be stopped
#                 pass
        
#         return f"⏹️ Stopped {stopped_count} out of {len(nodes)} nodes in project '{project_name}'"
        
#     except Exception as e:
#         return f"❌ Error stopping nodes: {str(e)}"

# def main():
#     """Entry point for the GNS3 MCP server"""
#     mcp.run(transport='stdio')

# if __name__ == "__main__":
#     main()

#!/usr/bin/env python3
from typing import Any, Dict, Optional
import time
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("gns3")

# ---------- HTTP helpers ----------
def _client(user: Optional[str], password: Optional[str]) -> httpx.Client:
    auth = (user, password) if user and password else None
    return httpx.Client(auth=auth, headers={"Accept": "application/json", "Content-Type": "application/json"}, timeout=30.0)

def gns3_get(c: httpx.Client, url: str) -> Dict[str, Any]:
    r = c.get(url); r.raise_for_status(); return r.json()

def gns3_post(c: httpx.Client, url: str, json: Optional[dict] = None) -> Dict[str, Any]:
    r = c.post(url, json=json or {}); r.raise_for_status(); return r.json() if r.text else {}

# ---------- Core ops (adapted from your CLI script) ----------
def find_project_id(c: httpx.Client, base: str, project_name: str) -> str:
    for p in gns3_get(c, f"{base}/v2/projects"):
        if p.get("name") == project_name:
            return p["project_id"]
    raise ValueError(f"Project '{project_name}' not found at {base}/v2/projects")

def get_template_map(c: httpx.Client, base: str) -> Dict[str, str]:
    templates = gns3_get(c, f"{base}/v2/templates")
    return {t.get("name"): t.get("template_id") for t in templates}

def add_node_from_template(c: httpx.Client, base: str, project_id: str, template_id: str, name: str, x: int, y: int) -> Dict[str, Any]:
    node = gns3_post(c, f"{base}/v2/projects/{project_id}/templates/{template_id}", json={"compute_id": "local", "x": x, "y": y, "name": name})
    node_id = node.get("node_id")
    if not node_id:
        raise RuntimeError(f"Failed to create node from template {template_id}: {node}")
    return node

def link_to_switch(c: httpx.Client, base: str, project_id: str, switch_id: str, device_id: str, switch_port: int,
                   device_adapter: int = 0, device_port: int = 0, switch_adapter: int = 0) -> Dict[str, Any]:
    payload = {
        "nodes": [
            {"node_id": device_id, "adapter_number": device_adapter, "port_number": device_port},
            {"node_id": switch_id, "adapter_number": switch_adapter, "port_number": switch_port},
        ]
    }
    return gns3_post(c, f"{base}/v2/projects/{project_id}/links", json=payload)

def start_node(c: httpx.Client, base: str, project_id: str, node_id: str) -> bool:
    try:
        gns3_post(c, f"{base}/v2/projects/{project_id}/nodes/{node_id}/start")
        return True
    except httpx.HTTPStatusError:
        # Some nodes (e.g., Ethernet switch) may auto‑start or not support /start
        return False

# ---------- Tools ----------
@mcp.tool()
def list_projects(server: str, user: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    """List GNS3 projects on the server.

    Args:
        server: GNS3 base URL, e.g. "http://127.0.0.1:3080"
        user: HTTP basic auth username if required
        password: HTTP basic auth password if required
    """
    base = server.rstrip("/")
    with _client(user, password) as c:
        return {"projects": gns3_get(c, f"{base}/v2/projects")}

@mcp.tool()
def list_templates(server: str, user: Optional[str] = None, password: Optional[str] = None) -> Dict[str, str]:
    """List available template names -> template IDs.

    Args:
        server: GNS3 base URL
        user: HTTP basic auth username if required
        password: HTTP basic auth password if required
    """
    base = server.rstrip("/")
    with _client(user, password) as c:
        return get_template_map(c, base)

@mcp.tool()
def create_topology(
    server: str,
    project: str,
    firewall_template: str,
    workstation_template: str,
    switch_template: str = "Ethernet switch",
    firewalls: int = 2,
    workstations: int = 3,
    x0: int = 100,
    y0: int = 100,
    xstep: int = 180,
    ystep: int = 130,
    per_row: int = 6,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a simple grid topology and link all devices to one switch, then start them.

    Args:
        server: GNS3 base URL (e.g., "http://127.0.0.1:3080")
        project: Existing project name
        firewall_template: Template name for firewalls (exact)
        workstation_template: Template name for workstations (exact)
        switch_template: Template name for the switch (default "Ethernet switch")
        firewalls: Number of firewall nodes
        workstations: Number of workstation nodes
        x0, y0, xstep, ystep, per_row: Layout controls
        user, password: Optional HTTP basic auth
    """
    base = server.rstrip("/")
    with _client(user, password) as c:
        project_id = find_project_id(c, base, project)
        tmap = get_template_map(c, base)

        def _ensure(name: str) -> str:
            if name not in tmap:
                raise ValueError(f"Template '{name}' not found. Available: {sorted(tmap.keys())}")
            return tmap[name]

        fw_tid = _ensure(firewall_template)
        ws_tid = _ensure(workstation_template)
        sw_tid = _ensure(switch_template)

        # Place switch centered above the grid
        total_devices = int(firewalls) + int(workstations)
        switch_x = x0 + (xstep * min(per_row, total_devices)) // 2
        switch_y = y0
        switch_node = add_node_from_template(c, base, project_id, sw_tid, "Core-Switch", switch_x, switch_y)
        switch_id = switch_node["node_id"]

        def grid_pos(i: int) -> tuple[int, int]:
            row, col = divmod(i, per_row)
            return x0 + col * xstep, y0 + ystep * (row + 1)

        created = []
        idx = 0
        for i in range(firewalls):
            name = f"FW-{i+1}"
            x, y = grid_pos(idx); idx += 1
            n = add_node_from_template(c, base, project_id, fw_tid, name, x, y)
            created.append({"name": name, "node_id": n["node_id"], "x": x, "y": y})

        for i in range(workstations):
            name = f"WS-{i+1}"
            x, y = grid_pos(idx); idx += 1
            n = add_node_from_template(c, base, project_id, ws_tid, name, x, y)
            created.append({"name": name, "node_id": n["node_id"], "x": x, "y": y})

        # Link each device to the switch on successive ports
        port = 0
        links = []
        for n in created:
            links.append(link_to_switch(c, base, project_id, switch_id, n["node_id"], port))
            port += 1
            time.sleep(0.05)  # small pacing

        # Start nodes (switch may ignore /start)
        started = 0
        for n in created + [{"name": "Core-Switch", "node_id": switch_id}]:
            if start_node(c, base, project_id, n["node_id"]):
                started += 1

        return {
            "project_id": project_id,
            "switch_id": switch_id,
            "devices_created": len(created),
            "nodes_started": started,
            "links_created": len(links),
        }

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
