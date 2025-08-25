"""
GNS3 MCP Server

This MCP server provides tools for creating and managing network topologies in GNS3
using natural language commands. It wraps the GNS3 API to allow users to describe
network topologies in plain English.
"""

import time
import requests
from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("gns3")

# Global session for GNS3 API calls
gns3_session = requests.Session()
gns3_session.headers.update({
    "Accept": "application/json", 
    "Content-Type": "application/json"
})

def gns3_get(url: str) -> Dict[str, Any]:
    """Make a GET request to GNS3 API"""
    r = gns3_session.get(url)
    r.raise_for_status()
    return r.json()

def gns3_post(url: str, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Make a POST request to GNS3 API"""
    r = gns3_session.post(url, json=json_data or {})
    r.raise_for_status()
    return r.json() if r.text else {}

def find_project_id(base_url: str, project_name: str) -> str:
    """Find project ID by name"""
    projects = gns3_get(f"{base_url}/v2/projects")
    for p in projects:
        if p.get("name") == project_name:
            return p["project_id"]
    raise ValueError(f"Project named '{project_name}' not found")

def get_template_map(base_url: str) -> Dict[str, str]:
    """Get mapping of template names to IDs"""
    templates = gns3_get(f"{base_url}/v2/templates")
    return {t.get("name"): t.get("template_id") for t in templates}

def add_node_from_template(base_url: str, project_id: str, template_id: str, name: str, x: int, y: int) -> Dict[str, Any]:
    """Add a node from template"""
    url = f"{base_url}/v2/projects/{project_id}/templates/{template_id}"
    payload = {"compute_id": "local", "x": x, "y": y, "name": name}
    return gns3_post(url, json=payload)

def link_nodes(base_url: str, project_id: str, node1_id: str, node2_id: str, 
               node1_adapter: int = 0, node1_port: int = 0,
               node2_adapter: int = 0, node2_port: int = 0) -> Dict[str, Any]:
    """Link two nodes together"""
    url = f"{base_url}/v2/projects/{project_id}/links"
    payload = {
        "nodes": [
            {"node_id": node1_id, "adapter_number": node1_adapter, "port_number": node1_port},
            {"node_id": node2_id, "adapter_number": node2_adapter, "port_number": node2_port},
        ]
    }
    return gns3_post(url, json=payload)

def start_node(base_url: str, project_id: str, node_id: str) -> bool:
    """Start a node"""
    url = f"{base_url}/v2/projects/{project_id}/nodes/{node_id}/start"
    try:
        gns3_post(url)
        return True
    except requests.HTTPError:
        # Some nodes may auto-start or not support /start
        return False

@mcp.tool()
async def connect_to_gns3(server_url: str = "http://172.16.194.129:80", 
                          username: Optional[str] = None, 
                          password: Optional[str] = None) -> str:
    """Connect to a GNS3 server and configure authentication.
    
    Args:
        server_url: GNS3 server URL (default: http://172.16.194.129:80)
        username: Basic auth username (optional)
        password: Basic auth password (optional)
    """
    global gns3_session
    
    # Configure authentication if provided
    if username and password:
        gns3_session.auth = (username, password)
    
    # Test connection
    try:
        projects = gns3_get(f"{server_url.rstrip('/')}/v2/projects")
        return f"Successfully connected to GNS3 server at {server_url}. Found {len(projects)} projects."
    except Exception as e:
        return f"Failed to connect to GNS3 server: {str(e)}"

@mcp.tool()
async def list_projects(server_url: str = "http://172.16.194.129:80") -> str:
    """List all available projects on the GNS3 server.
    
    Args:
        server_url: GNS3 server URL
    """
    try:
        projects = gns3_get(f"{server_url.rstrip('/')}/v2/projects")
        if not projects:
            return "No projects found on the server."
        
        project_list = []
        for p in projects:
            project_list.append(f"- {p.get('name', 'Unknown')} (ID: {p.get('project_id', 'Unknown')})")
        
        return f"Available projects:\n" + "\n".join(project_list)
    except Exception as e:
        return f"Error listing projects: {str(e)}"

@mcp.tool()
async def list_templates(server_url: str = "http://172.16.194.129:80") -> str:
    """List all available templates on the GNS3 server.
    
    Args:
        server_url: GNS3 server URL
    """
    try:
        templates = gns3_get(f"{server_url.rstrip('/')}/v2/templates")
        if not templates:
            return "No templates found on the server."
        
        template_list = []
        for t in templates:
            template_list.append(f"- {t.get('name', 'Unknown')} (ID: {t.get('template_id', 'Unknown')})")
        
        return f"Available templates:\n" + "\n".join(template_list)
    except Exception as e:
        return f"Error listing templates: {str(e)}"

@mcp.tool()
async def create_simple_topology(project_name: str,
                                firewalls: int = 2,
                                workstations: int = 3,
                                firewall_template: str = "Firewall Docker",
                                workstation_template: str = "Workstation Docker",
                                switch_template: str = "Ethernet switch",
                                server_url: str = "http://172.16.194.129:80",
                                start_x: int = 100,
                                start_y: int = 100,
                                x_spacing: int = 180,
                                y_spacing: int = 130,
                                devices_per_row: int = 6) -> str:
    """Create a simple network topology with firewalls, workstations, and a switch.
    
    Args:
        project_name: Name of the existing GNS3 project
        firewalls: Number of firewall nodes to create
        workstations: Number of workstation nodes to create
        firewall_template: Template name for firewall nodes
        workstation_template: Template name for workstation nodes
        switch_template: Template name for the switch
        server_url: GNS3 server URL
        start_x: Starting X coordinate for layout
        start_y: Starting Y coordinate for layout
        x_spacing: Horizontal spacing between nodes
        y_spacing: Vertical spacing between rows
        devices_per_row: Maximum devices per row in the layout
    """
    try:
        base_url = server_url.rstrip('/')
        
        # Find project
        project_id = find_project_id(base_url, project_name)
        
        # Get templates
        template_map = get_template_map(base_url)
        fw_tid = template_map.get(firewall_template)
        ws_tid = template_map.get(workstation_template)
        sw_tid = template_map.get(switch_template)
        
        if not fw_tid:
            return f"Firewall template '{firewall_template}' not found. Available: {', '.join(sorted(template_map.keys()))}"
        if not ws_tid:
            return f"Workstation template '{workstation_template}' not found. Available: {', '.join(sorted(template_map.keys()))}"
        if not sw_tid:
            return f"Switch template '{switch_template}' not found. Available: {', '.join(sorted(template_map.keys()))}"
        
        # Create switch
        switch_x = start_x + (x_spacing * min(devices_per_row, firewalls + workstations)) // 2
        switch_y = start_y
        switch_node = add_node_from_template(base_url, project_id, sw_tid, "Core-Switch", switch_x, switch_y)
        switch_id = switch_node["node_id"]
        
        # Create nodes
        created_nodes = []
        current_index = 0
        
        def grid_pos(idx):
            row = idx // devices_per_row
            col = idx % devices_per_row
            x = start_x + col * x_spacing
            y = start_y + y_spacing * (row + 1)
            return x, y
        
        # Create firewalls
        for i in range(firewalls):
            name = f"FW-{i+1}"
            x, y = grid_pos(current_index)
            node = add_node_from_template(base_url, project_id, fw_tid, name, x, y)
            created_nodes.append((node["node_id"], name))
            current_index += 1
        
        # Create workstations
        for i in range(workstations):
            name = f"WS-{i+1}"
            x, y = grid_pos(current_index)
            node = add_node_from_template(base_url, project_id, ws_tid, name, x, y)
            created_nodes.append((node["node_id"], name))
            current_index += 1
        
        # Link all devices to switch
        switch_port = 0
        for node_id, name in created_nodes:
            link = link_nodes(base_url, project_id, switch_id, node_id, switch_port=switch_port)
            switch_port += 1
            time.sleep(0.05)  # Small delay to avoid overwhelming server
        
        # Start nodes
        started = 0
        for node_id, name in created_nodes + [(switch_id, "Core-Switch")]:
            if start_node(base_url, project_id, node_id):
                started += 1
        
        return f"Successfully created topology:\n" \
               f"- Created {len(created_nodes)} devices ({firewalls} firewalls, {workstations} workstations)\n" \
               f"- Created 1 switch\n" \
               f"- Linked all devices to the switch\n" \
               f"- Started {started} nodes"
               
    except Exception as e:
        return f"Error creating topology: {str(e)}"

@mcp.tool()
async def create_custom_topology(project_name: str,
                                topology_description: str,
                                server_url: str = "http://172.16.194.129:80") -> str:
    """Create a custom topology based on a natural language description.
    
    Args:
        project_name: Name of the existing GNS3 project
        topology_description: Natural language description of the topology to create
        server_url: GNS3 server URL
    """
    try:
        base_url = server_url.rstrip('/')
        
        # Find project
        project_id = find_project_id(base_url, project_name)
        
        # Get available templates
        template_map = get_template_map(base_url)
        available_templates = list(template_map.keys())
        
        # For now, return a message with available templates
        # In a full implementation, you would use AI to parse the description
        # and create the appropriate topology
        return f"Custom topology creation based on: '{topology_description}'\n\n" \
               f"Available templates for reference:\n" + \
               "\n".join([f"- {template}" for template in available_templates]) + \
               "\n\nNote: This is a placeholder. Full implementation would parse the description " \
               "and create the appropriate topology automatically."
               
    except Exception as e:
        return f"Error creating custom topology: {str(e)}"

@mcp.tool()
async def start_project_nodes(project_name: str,
                             server_url: str = "http://172.16.194.129:80") -> str:
    """Start all nodes in a project.
    
    Args:
        project_name: Name of the GNS3 project
        server_url: GNS3 server URL
    """
    try:
        base_url = server_url.rstrip('/')
        project_id = find_project_id(base_url, project_name)
        
        # Get all nodes in the project
        nodes = gns3_get(f"{base_url}/v2/projects/{project_id}/nodes")
        
        started_count = 0
        for node in nodes:
            node_id = node["node_id"]
            node_name = node.get("name", "Unknown")
            if start_node(base_url, project_id, node_id):
                started_count += 1
        
        return f"Started {started_count} out of {len(nodes)} nodes in project '{project_name}'"
        
    except Exception as e:
        return f"Error starting nodes: {str(e)}"

@mcp.tool()
async def stop_project_nodes(project_name: str,
                            server_url: str = "http://172.16.194.129:80") -> str:
    """Stop all nodes in a project.
    
    Args:
        project_name: Name of the GNS3 project
        server_url: GNS3 server URL
    """
    try:
        base_url = server_url.rstrip('/')
        project_id = find_project_id(base_url, project_name)
        
        # Get all nodes in the project
        nodes = gns3_get(f"{base_url}/v2/projects/{project_id}/nodes")
        
        stopped_count = 0
        for node in nodes:
            node_id = node["node_id"]
            node_name = node.get("name", "Unknown")
            try:
                url = f"{base_url}/v2/projects/{project_id}/nodes/{node_id}/stop"
                gns3_post(url)
                stopped_count += 1
            except requests.HTTPError:
                # Some nodes may not support stop or already be stopped
                pass
        
        return f"Stopped {stopped_count} out of {len(nodes)} nodes in project '{project_name}'"
        
    except Exception as e:
        return f"Error stopping nodes: {str(e)}"

def main():
    """Entry point for the GNS3 MCP server"""
    mcp.run(transport='stdio')

if __name__ == "__main__":
    main()
