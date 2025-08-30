#!/usr/bin/env python3
"""
GNS3 MCP Server (FastMCP + httpx, async)

Implements read + control tools inspired by the legacy GNS3 wrapper:
- GetProject(s), GetTemplate(s), GetNode(s), GetLink(s)
- StartNode, StopNode, ReloadNode, SuspendNode
- StartAllNodes, StopAllNodes
- NodeSummary, NodeInventory, LinkSummary
- CreateTopology, CreateVPCSNetwork (NEW - for topology creation)

Design notes:
- Pure STDIO (no prints to stdout). Return values or raise exceptions.
- Auth: optional HTTP Basic via user/password.
- Timeouts + clear errors.
- All tools documented so the MCP client (LLM) can self-figure usage.

References:
- Weather FastMCP shape & async style.  # (matches this repo's sample)
- GNS3 REST shapes / summaries from legacy module.  # (we adopt endpoints/summary math)
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import asyncio
import time
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("gns3")

# ------------------------------- HTTP helpers -------------------------------

def _auth(user: Optional[str], password: Optional[str]) -> Optional[tuple[str, str]]:
    return (user, password) if user and password else None

def _base(server: str) -> str:
    server = server.rstrip("/")
    return f"{server}/v2"

class GNSError(RuntimeError):
    pass

async def _aget(client: httpx.AsyncClient, url: str) -> Any:
    r = await client.get(url)
    r.raise_for_status()
    return r.json()

async def _apost(client: httpx.AsyncClient, url: str, json: Optional[dict] = None) -> Any:
    r = await client.post(url, json=json or {})
    r.raise_for_status()
    return r.json() if r.text else {}

# ------------------------------- Core queries --------------------------------

async def _projects(client: httpx.AsyncClient, base: str) -> List[dict]:
    return await _aget(client, f"{base}/projects")

async def _project_by_name_or_id(client: httpx.AsyncClient, base: str, *, name: Optional[str], project_id: Optional[str]) -> dict:
    if project_id:
        return await _aget(client, f"{base}/projects/{project_id}")
    if name:
        for p in await _projects(client, base):
            if p.get("name") == name:
                return p
        raise GNSError(f"Project not found: {name}")
    raise GNSError("Provide either 'name' or 'project_id'.")

async def _templates(client: httpx.AsyncClient, base: str) -> List[dict]:
    return await _aget(client, f"{base}/templates")

async def _template_by_name_or_id(client: httpx.AsyncClient, base: str, *, name: Optional[str], template_id: Optional[str]) -> dict:
    if template_id:
        return await _aget(client, f"{base}/templates/{template_id}")
    if name:
        for t in await _templates(client, base):
            if t.get("name") == name:
                return t
        raise GNSError(f"Template not found: {name}")
    raise GNSError("Provide either 'name' or 'template_id'.")

async def _nodes(client: httpx.AsyncClient, base: str, project_id: str) -> List[dict]:
    return await _aget(client, f"{base}/projects/{project_id}/nodes")

async def _node(client: httpx.AsyncClient, base: str, project_id: str, node_id: str) -> dict:
    return await _aget(client, f"{base}/projects/{project_id}/nodes/{node_id}")

async def _links(client: httpx.AsyncClient, base: str, project_id: str) -> List[dict]:
    return await _aget(client, f"{base}/projects/{project_id}/links")

async def _link(client: httpx.AsyncClient, base: str, project_id: str, link_id: str) -> dict:
    return await _aget(client, f"{base}/projects/{project_id}/links/{link_id}")

# ------------------------------- Node controls -------------------------------

async def _node_action(client: httpx.AsyncClient, base: str, project_id: str, node_id: str, action: str) -> dict:
    # POST /projects/{project_id}/nodes/{node_id}/{action}
    return await _apost(client, f"{base}/projects/{project_id}/nodes/{node_id}/{action}")

async def _project_nodes_action(client: httpx.AsyncClient, base: str, project_id: str, action: str) -> dict | None:
    # POST /projects/{project_id}/nodes/{action}
    # start | stop | reload | suspend
    return await _apost(client, f"{base}/projects/{project_id}/nodes/{action}")

# ------------------------------- Topology creation helpers -------------------------------

async def _add_node_from_template(client: httpx.AsyncClient, base: str, project_id: str, template_id: str, name: str, x: int, y: int) -> Dict[str, Any]:
    """Add a node from template to a project"""
    url = f"{base}/projects/{project_id}/templates/{template_id}"
    payload = {"compute_id": "local", "x": x, "y": y, "name": name}
    node = await _apost(client, url, json=payload)
    node_id = node.get("node_id")
    if not node_id:
        raise GNSError(f"Failed to create node from template {template_id}: {node}")
    return node

async def _link_nodes(client: httpx.AsyncClient, base: str, project_id: str, node1_id: str, node2_id: str, 
                      node1_adapter: int = 0, node1_port: int = 0,
                      node2_adapter: int = 0, node2_port: int = 0) -> Dict[str, Any]:
    """Link two nodes together"""
    url = f"{base}/projects/{project_id}/links"
    payload = {
        "nodes": [
            {"node_id": node1_id, "adapter_number": node1_adapter, "port_number": node1_port},
            {"node_id": node2_id, "adapter_number": node2_adapter, "port_number": node2_port},
        ]
    }
    return await _apost(client, url, json=payload)

async def _start_node(client: httpx.AsyncClient, base: str, project_id: str, node_id: str) -> bool:
    """Start a node, returns True if successful"""
    try:
        await _node_action(client, base, project_id, node_id, "start")
        return True
    except httpx.HTTPStatusError:
        # Some nodes may auto-start or not support /start
        return False

# ------------------------------- Summaries -----------------------------------

def _nodes_summary(nodes: List[dict]) -> List[Tuple[str, str, Optional[int], str]]:
    """
    Produce tuples: (name, status, console_port, node_id)
    Mirrors legacy nodes_summary intent. 
    """
    out: List[Tuple[str, str, Optional[int], str]] = []
    for n in nodes:
        out.append((n.get("name"), n.get("status"), n.get("console"), n.get("node_id")))
    return out  # e.g., [(name, status, console, node_id), ...]

def _nodes_inventory(server_host: str, nodes: List[dict]) -> Dict[str, dict]:
    """
    Produce inventory keyed by node name, like the legacy nodes_inventory:
    { name: {server, name, console_port, console_type, type, template} }
    """
    inv: Dict[str, dict] = {}
    for n in nodes:
        inv[n["name"]] = {
            "server": server_host,
            "name": n["name"],
            "console_port": n.get("console"),
            "console_type": n.get("console_type"),
            "type": n.get("node_type"),
            "template": n.get("template"),
        }
    return inv

def _links_summary(nodes: List[dict], links: List[dict]) -> List[Tuple[str, str, str, str]]:
    """
    Produce tuples: (node_a, port_name_a, node_b, port_name_b)
    Port name resolution uses node.ports[] (adapter_number + port_number => name),
    following the legacy logic.
    """
    # Build helper maps
    node_by_id = {n["node_id"]: n for n in nodes}
    port_name_map = {}
    for n in nodes:
        port_name_map[n["node_id"]] = {}
        for p in n.get("ports", []) or []:
            key = (p.get("adapter_number"), p.get("port_number"))
            port_name_map[n["node_id"]][key] = p.get("name")
    out: List[Tuple[str, str, str, str]] = []
    for l in links:
        if not l.get("nodes"):
            continue
        a, b = l["nodes"][0], l["nodes"][1]
        na, nb = node_by_id.get(a["node_id"]), node_by_id.get(b["node_id"])
        if not na or not nb:
            continue
        pa = port_name_map.get(na["node_id"], {}).get((a.get("adapter_number"), a.get("port_number")), f"{a.get('adapter_number')}/{a.get('port_number')}")
        pb = port_name_map.get(nb["node_id"], {}).get((b.get("adapter_number"), b.get("port_number")), f"{b.get('adapter_number')}/{b.get('port_number')}")
        out.append((na.get("name"), pa, nb.get("name"), pb))
    return out

# ------------------------------- Tools ---------------------------------------

@mcp.tool()
async def get_projects(server: str, user: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    """List all projects.

    Args:
        server: Base URL to GNS3 (e.g., "http://127.0.0.1:3080")
        user: Optional HTTP basic user
        password: Optional HTTP basic password
    """
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=30.0) as c:
        return {"projects": await _projects(c, base)}

@mcp.tool()
async def get_project(server: str, name: Optional[str] = None, project_id: Optional[str] = None,
                      user: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    """Get a single project by name or ID."""
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=30.0) as c:
        return await _project_by_name_or_id(c, base, name=name, project_id=project_id)

@mcp.tool()
async def get_templates(server: str, user: Optional[str] = None, password: Optional[str] = None) -> Dict[str, str]:
    """List template names -> IDs."""
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=30.0) as c:
        tmpl = await _templates(c, base)
        return {t.get("name"): t.get("template_id") for t in tmpl}

@mcp.tool()
async def get_template(server: str, name: Optional[str] = None, template_id: Optional[str] = None,
                       user: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    """Get a single template by name or ID."""
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=30.0) as c:
        return await _template_by_name_or_id(c, base, name=name, template_id=template_id)

@mcp.tool()
async def get_nodes(server: str, project_id: str, user: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    """List nodes in a project."""
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=30.0) as c:
        return {"nodes": await _nodes(c, base, project_id)}

@mcp.tool()
async def get_node(server: str, project_id: str, node_id: str, user: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    """Get a single node by ID."""
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=30.0) as c:
        return await _node(c, base, project_id, node_id)

@mcp.tool()
async def get_links(server: str, project_id: str, user: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    """List links in a project."""
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=30.0) as c:
        return {"links": await _links(c, base, project_id)}

@mcp.tool()
async def get_link(server: str, project_id: str, link_id: str, user: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    """Get a single link by ID."""
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=30.0) as c:
        return await _link(c, base, project_id, link_id)

@mcp.tool()
async def start_node(server: str, project_id: str, node_id: str, user: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    """POST /nodes/{node_id}/start"""
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=60.0) as c:
        return await _node_action(c, base, project_id, node_id, "start")

@mcp.tool()
async def stop_node(server: str, project_id: str, node_id: str, user: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    """POST /nodes/{node_id}/stop"""
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=60.0) as c:
        return await _node_action(c, base, project_id, node_id, "stop")

@mcp.tool()
async def reload_node(server: str, project_id: str, node_id: str, user: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    """POST /nodes/{node_id}/reload"""
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=60.0) as c:
        return await _node_action(c, base, project_id, node_id, "reload")

@mcp.tool()
async def suspend_node(server: str, project_id: str, node_id: str, user: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    """POST /nodes/{node_id}/suspend"""
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=60.0) as c:
        return await _node_action(c, base, project_id, node_id, "suspend")

@mcp.tool()
async def start_all_nodes(server: str, project_id: str, user: Optional[str] = None, password: Optional[str] = None) -> str:
    """POST /projects/{project_id}/nodes/start — starts all nodes in the project."""
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=120.0) as c:
        await _project_nodes_action(c, base, project_id, "start")
        return "OK"

@mcp.tool()
async def stop_all_nodes(server: str, project_id: str, user: Optional[str] = None, password: Optional[str] = None) -> str:
    """POST /projects/{project_id}/nodes/stop — stops all nodes in the project."""
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=120.0) as c:
        await _project_nodes_action(c, base, project_id, "stop")
        return "OK"

@mcp.tool()
async def node_summary(server: str, project_id: str, user: Optional[str] = None, password: Optional[str] = None) -> List[Tuple[str, str, Optional[int], str]]:
    """Summary tuples: (name, status, console_port, node_id)."""
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=30.0) as c:
        ns = _nodes_summary(await _nodes(c, base, project_id))
        return ns

@mcp.tool()
async def node_inventory(server: str, project_id: str, user: Optional[str] = None, password: Optional[str] = None) -> Dict[str, dict]:
    """Inventory dict keyed by node name: {name: {server, name, console_port, console_type, type, template}}."""
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=30.0) as c:
        nodes = await _nodes(c, base, project_id)
        # Extract host (simple parse without extra deps)
        try:
            server_host = server.split("://", 1)[1].split("/", 1)[0].split(":")[0]
        except Exception:
            server_host = "unknown"
        return _nodes_inventory(server_host, nodes)

@mcp.tool()
async def link_summary(server: str, project_id: str, user: Optional[str] = None, password: Optional[str] = None) -> List[Tuple[str, str, str, str]]:
    """Summary tuples for links: (node_a, port_name_a, node_b, port_name_b)."""
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=30.0) as c:
        nodes = await _nodes(c, base, project_id)
        links = await _links(c, base, project_id)
        return _links_summary(nodes, links)

# ------------------------------- Topology Creation Tools -------------------------------

@mcp.tool()
async def create_topology(
    server: str,
    project_name: str,
    node_configs: List[Dict[str, Any]],
    switch_template: str = "Ethernet switch",
    layout_type: str = "grid",
    start_x: int = 100,
    start_y: int = 100,
    x_spacing: int = 180,
    y_spacing: int = 130,
    devices_per_row: int = 6,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a complete network topology with any combination of node types connected to a central switch.
    
    This is the PRIMARY tool for creating network topologies. It handles the entire workflow:
    connection, node creation, linking, and starting. No need to call other tools first.
    
    USAGE GUIDE FOR LLMs:
    - Use this tool when you want to create a network with multiple different types of devices
    - The node_configs parameter defines what devices to create and how many of each
    - All devices will be automatically connected to a central switch
    - Devices are arranged in a grid layout by default
    
    EXAMPLES:
    1. Create a simple network with 2 firewalls and 3 workstations:
       node_configs = [
           {"template": "Firewall Docker", "count": 2, "name_prefix": "FW"},
           {"template": "Workstation Docker", "count": 3, "name_prefix": "WS"}
       ]
    
    2. Create a network with routers, switches, and PCs:
       node_configs = [
           {"template": "Cisco Router", "count": 2, "name_prefix": "Router"},
           {"template": "Cisco Switch", "count": 1, "name_prefix": "Switch"},
           {"template": "VPCS", "count": 4, "name_prefix": "PC"}
       ]
    
    Args:
        server: GNS3 server URL (e.g., "http://127.0.0.1:3080")
        project_name: Name of the existing GNS3 project
        node_configs: List of node configurations. Each config should have:
            - template: Template name (exact match required)
            - count: Number of nodes to create
            - name_prefix: Prefix for node names (e.g., "FW" creates "FW-1", "FW-2")
        switch_template: Template name for the central switch (default: "Ethernet switch")
        layout_type: Layout style - "grid" (default) or "horizontal"
        start_x: Starting X coordinate for layout
        start_y: Starting Y coordinate for layout
        x_spacing: Horizontal spacing between nodes
        y_spacing: Vertical spacing between rows
        devices_per_row: Maximum devices per row in grid layout
        user: Optional HTTP basic auth username
        password: Optional HTTP basic auth password
    """
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=120.0) as c:
        try:
            # Step 1: Find project
            project = await _project_by_name_or_id(c, base, name=project_name, project_id=None)
            project_id = project["project_id"]
            
            # Step 2: Get templates
            templates = await _templates(c, base)
            template_map = {t.get("name"): t.get("template_id") for t in templates}
            
            # Validate switch template
            sw_tid = template_map.get(switch_template)
            if not sw_tid:
                raise GNSError(f"Switch template '{switch_template}' not found. Available: {', '.join(sorted(template_map.keys()))}")
            
            # Validate all node templates
            total_devices = 0
            validated_configs = []
            for config in node_configs:
                template_name = config["template"]
                template_id = template_map.get(template_name)
                if not template_id:
                    raise GNSError(f"Template '{template_name}' not found. Available: {', '.join(sorted(template_map.keys()))}")
                
                validated_configs.append({
                    **config,
                    "template_id": template_id
                })
                total_devices += config["count"]
            
            # Step 3: Create switch
            if layout_type == "grid":
                switch_x = start_x + (x_spacing * min(devices_per_row, total_devices)) // 2
                switch_y = start_y
            else:  # horizontal layout
                switch_x = start_x + (x_spacing * total_devices) // 2
                switch_y = start_y
            
            switch_node = await _add_node_from_template(c, base, project_id, sw_tid, "Core-Switch", switch_x, switch_y)
            switch_id = switch_node["node_id"]
            
            # Step 4: Create nodes in specified layout
            created_nodes = []
            current_index = 0
            
            def grid_pos(idx):
                row = idx // devices_per_row
                col = idx % devices_per_row
                x = start_x + col * x_spacing
                y = start_y + y_spacing * (row + 1)
                return x, y
            
            def horizontal_pos(idx):
                x = start_x + idx * x_spacing
                y = start_y + y_spacing
                return x, y
            
            # Create nodes based on layout type
            for config in validated_configs:
                template_id = config["template_id"]
                count = config["count"]
                name_prefix = config["name_prefix"]
                
                for i in range(count):
                    name = f"{name_prefix}-{i+1}"
                    if layout_type == "grid":
                        x, y = grid_pos(current_index)
                    else:
                        x, y = horizontal_pos(current_index)
                    
                    node = await _add_node_from_template(c, base, project_id, template_id, name, x, y)
                    created_nodes.append({
                        "name": name,
                        "node_id": node["node_id"],
                        "x": x,
                        "y": y,
                        "template": config["template"]
                    })
                    current_index += 1
            
            # Step 5: Link all devices to switch
            switch_port = 0
            links_created = []
            for node in created_nodes:
                link = await _link_nodes(c, base, project_id, switch_id, node["node_id"], switch_port=switch_port)
                links_created.append(link)
                switch_port += 1
                await asyncio.sleep(0.05)  # Small delay to avoid overwhelming server
            
            # Step 6: Start nodes
            started = 0
            for node in created_nodes + [{"name": "Core-Switch", "node_id": switch_id}]:
                if await _start_node(c, base, project_id, node["node_id"]):
                    started += 1
            
            # Build summary
            node_summary = []
            for config in node_configs:
                node_summary.append(f"{config['count']} {config['name_prefix']}")
            
            return {
                "success": True,
                "project_id": project_id,
                "switch_id": switch_id,
                "devices_created": len(created_nodes),
                "nodes_started": started,
                "links_created": len(links_created),
                "layout_type": layout_type,
                "node_summary": ", ".join(node_summary),
                "summary": f"Created {len(created_nodes)} devices ({', '.join(node_summary)}), 1 switch, {len(links_created)} links, started {started} nodes"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

@mcp.tool()
async def create_simple_network(
    server: str,
    project_name: str,
    template_name: str,
    node_count: int = 2,
    switch_template: str = "Ethernet switch",
    layout: str = "horizontal",
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a simple network with multiple nodes of the same type connected to a switch.
    
    This is a SIMPLIFIED tool for creating basic networks. Use this when you want:
    - Multiple nodes of the same type (e.g., 5 VPCS nodes)
    - Simple horizontal or grid layout
    - Quick setup without complex configuration
    
    USAGE GUIDE FOR LLMs:
    - Use this tool for simple networks with one type of device
    - Use create_topology for networks with multiple device types
    - Use create_vpcs_network specifically for VPCS networks
    
    EXAMPLES:
    1. Create 4 VPCS nodes: template_name="VPCS", node_count=4
    2. Create 3 routers: template_name="Cisco Router", node_count=3
    3. Create 2 switches: template_name="Cisco Switch", node_count=2
    
    Args:
        server: GNS3 server URL (e.g., "http://127.0.0.1:3080")
        project_name: Name of the existing GNS3 project
        template_name: Template name for the nodes (exact match required)
        node_count: Number of nodes to create
        switch_template: Template name for the switch (default: "Ethernet switch")
        layout: Layout style - "horizontal" (default) or "grid"
        user: Optional HTTP basic auth username
        password: Optional HTTP basic auth password
    """
    # Convert to the generic format
    node_configs = [{
        "template": template_name,
        "count": node_count,
        "name_prefix": template_name.split()[0]  # Use first word of template as prefix
    }]
    
    return await create_topology(
        server=server,
        project_name=project_name,
        node_configs=node_configs,
        switch_template=switch_template,
        layout_type=layout,
        user=user,
        password=password
    )

@mcp.tool()
async def create_vpcs_network(
    server: str,
    project_name: str,
    vpcs_count: int = 2,
    vpcs_template: str = "VPCS",
    switch_template: str = "Ethernet switch",
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a VPCS network with the specified number of VPCS nodes connected to a switch.
    
    This is a SPECIALIZED tool specifically for VPCS networks. VPCS nodes are lightweight
    virtual PCs that are perfect for testing network connectivity and basic protocols.
    
    USAGE GUIDE FOR LLMs:
    - Use this tool specifically for VPCS networks
    - VPCS nodes are great for learning/testing network concepts
    - For other node types, use create_simple_network or create_topology
    
    EXAMPLES:
    1. Basic VPCS network: vpcs_count=2 (creates 2 VPCS nodes)
    2. Larger VPCS network: vpcs_count=8 (creates 8 VPCS nodes)
    3. Custom VPCS template: vpcs_template="VPCS Docker" (if you have a custom VPCS template)
    
    Args:
        server: GNS3 server URL (e.g., "http://127.0.0.1:3080")
        project_name: Name of the existing GNS3 project
        vpcs_count: Number of VPCS nodes to create (default: 2)
        vpcs_template: Template name for VPCS nodes (default: "VPCS")
        switch_template: Template name for the switch (default: "Ethernet switch")
        user: Optional HTTP basic auth username
        password: Optional HTTP basic auth password
    """
    # Use the simple network function for VPCS
    return await create_simple_network(
        server=server,
        project_name=project_name,
        template_name=vpcs_template,
        node_count=vpcs_count,
        switch_template=switch_template,
        layout="horizontal",
        user=user,
        password=password
    )

@mcp.tool()
async def create_custom_topology(
    server: str,
    project_name: str,
    topology_description: str,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    """Get guidance for creating a custom topology based on a natural language description.
    
    This tool provides guidance and available templates for creating complex topologies.
    Use this when you're unsure which tool to use or need help planning your topology.
    
    USAGE GUIDE FOR LLMs:
    - Use this tool when you need help understanding what's possible
    - It will show you available templates and suggest the right tool to use
    - After getting guidance, use create_topology or create_simple_network
    
    EXAMPLES:
    1. "I want to create a network with firewalls and workstations"
    2. "Create a topology with routers and switches"
    3. "I need a simple network with 5 PCs"
    
    Args:
        server: GNS3 server URL (e.g., "http://127.0.0.1:3080")
        project_name: Name of the existing GNS3 project
        topology_description: Natural language description of the topology to create
        user: Optional HTTP basic auth username
        password: Optional HTTP basic auth password
    """
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=30.0) as c:
        try:
            # Find project
            project = await _project_by_name_or_id(c, base, name=project_name, project_id=None)
            
            # Get available templates
            templates = await _templates(c, base)
            available_templates = [t.get("name") for t in templates if t.get("name")]
            
            # Provide specific guidance based on common patterns
            guidance = "Here are the recommended tools to use:\n\n"
            guidance += "🔧 For simple networks with one device type:\n"
            guidance += "   - Use 'create_simple_network' with template_name and node_count\n\n"
            guidance += "🌐 For complex networks with multiple device types:\n"
            guidance += "   - Use 'create_topology' with node_configs parameter\n\n"
            guidance += "💻 For VPCS networks specifically:\n"
            guidance += "   - Use 'create_vpcs_network' for lightweight virtual PCs\n\n"
            guidance += "📋 Available templates:\n"
            guidance += "   " + ", ".join(available_templates[:15])
            if len(available_templates) > 15:
                guidance += f" ... and {len(available_templates) - 15} more"
            
            return {
                "success": True,
                "project_id": project["project_id"],
                "topology_request": topology_description,
                "available_templates": available_templates,
                "guidance": guidance,
                "recommended_tool": "create_topology" if "multiple" in topology_description.lower() or "and" in topology_description.lower() else "create_simple_network"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
