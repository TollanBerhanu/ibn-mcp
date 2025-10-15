#!/usr/bin/env python3
"""
GNS3 MCP Server — FastMCP + async httpx

Tools included:
- get_project, get_projects
- get_template, get_templates
- get_node, get_nodes
- get_link, get_links
- start_node, stop_node, reload_node, suspend_node
- start_all_nodes, stop_all_nodes
- node_summary, node_inventory, link_summary
- create_node_from_template
- link_nodes

Design:
- Pure STDIO MCP (no prints to stdout).
- Optional HTTP Basic auth (user/password).
- Timeouts and clear exceptions.
- Docstrings explicitly describe purpose, param types, accepted forms, and examples.

Implementation references:
- REST shapes & summaries mirror the behavior in the legacy wrapper (projects/nodes/links, node actions, inventory/summary helpers).
- FastMCP patterns match the weather MCP example (async tools, type hints, docstrings, stdio run).
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple, Union
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("gns3")

# ------------------------------ HTTP helpers ------------------------------

def _auth(user: Optional[str], password: Optional[str]) -> Optional[tuple[str, str]]:
    return (user, password) if user and password else None

def _base(server: str) -> str:
    return f"{server.rstrip('/')}/v2"

async def _aget(c: httpx.AsyncClient, url: str) -> Any:
    r = await c.get(url)
    r.raise_for_status()
    return r.json()

async def _apost(c: httpx.AsyncClient, url: str, json: Optional[dict] = None) -> Any:
    r = await c.post(url, json=json or {})
    r.raise_for_status()
    return r.json() if r.text else {}

# ------------------------------ Core getters ------------------------------

async def _projects(c: httpx.AsyncClient, base: str) -> List[dict]:
    return await _aget(c, f"{base}/projects")

async def _project_by_name_or_id(c: httpx.AsyncClient, base: str,
                                 *, name: Optional[str], project_id: Optional[str]) -> dict:
    if project_id:
        return await _aget(c, f"{base}/projects/{project_id}")
    if name:
        for p in await _projects(c, base):
            if p.get("name") == name:
                return p
        raise ValueError(f"Project not found: {name}")
    raise ValueError("Provide either 'name' or 'project_id'.")


async def _templates(c: httpx.AsyncClient, base: str) -> List[dict]:
    return await _aget(c, f"{base}/templates")

async def _template_by_name_or_id(c: httpx.AsyncClient, base: str,
                                  *, name: Optional[str], template_id: Optional[str]) -> dict:
    if template_id:
        return await _aget(c, f"{base}/templates/{template_id}")
    if name:
        for t in await _templates(c, base):
            if t.get("name") == name:
                return t
        raise ValueError(f"Template not found: {name}")
    raise ValueError("Provide either 'name' or 'template_id'.")

async def _nodes(c: httpx.AsyncClient, base: str, project_id: str) -> List[dict]:
    return await _aget(c, f"{base}/projects/{project_id}/nodes")

async def _node(c: httpx.AsyncClient, base: str, project_id: str, node_id: str) -> dict:
    return await _aget(c, f"{base}/projects/{project_id}/nodes/{node_id}")

async def _links(c: httpx.AsyncClient, base: str, project_id: str) -> List[dict]:
    return await _aget(c, f"{base}/projects/{project_id}/links")

async def _link(c: httpx.AsyncClient, base: str, project_id: str, link_id: str) -> dict:
    return await _aget(c, f"{base}/projects/{project_id}/links/{link_id}")

# ------------------------------ Node actions ------------------------------

async def _node_action(c: httpx.AsyncClient, base: str, project_id: str, node_id: str, action: str) -> dict:
    # POST /projects/{project_id}/nodes/{node_id}/{action}
    return await _apost(c, f"{base}/projects/{project_id}/nodes/{node_id}/{action}")

async def _project_nodes_action(c: httpx.AsyncClient, base: str, project_id: str, action: str) -> None:
    # POST /projects/{project_id}/nodes/{action}
    await _apost(c, f"{base}/projects/{project_id}/nodes/{action}")

# ------------------------------ Summaries --------------------------------

def _nodes_summary(nodes: List[dict]) -> List[Tuple[str, str, Optional[int], str]]:
    """
    [(name, status, console_port, node_id)] — mirrors legacy nodes_summary.
    """
    out: List[Tuple[str, str, Optional[int], str]] = []
    for n in nodes:
        out.append((n.get("name"), n.get("status"), n.get("console"), n.get("node_id")))
    return out

def _nodes_inventory(server_host: str, nodes: List[dict]) -> Dict[str, dict]:
    """
    Inventory keyed by node name — mirrors legacy nodes_inventory:
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
    [(node_a, port_name_a, node_b, port_name_b)] — resolves adapter/port to port name
    using node.ports[]. Mirrors legacy link summary behavior.
    """
    node_by_id = {n["node_id"]: n for n in nodes}
    port_name_map = {}
    for n in nodes:
        mapping = {}
        for p in n.get("ports", []) or []:
            mapping[(p.get("adapter_number"), p.get("port_number"))] = p.get("name")
        port_name_map[n["node_id"]] = mapping

    out: List[Tuple[str, str, str, str]] = []
    for l in links:
        if not l.get("nodes"):
            continue
        a, b = l["nodes"][0], l["nodes"][1]
        na, nb = node_by_id.get(a["node_id"]), node_by_id.get(b["node_id"])
        if not na or not nb:
            continue
        pa = port_name_map.get(na["node_id"], {}).get((a.get("adapter_number"), a.get("port_number")),
                                                      f"{a.get('adapter_number')}/{a.get('port_number')}")
        pb = port_name_map.get(nb["node_id"], {}).get((b.get("adapter_number"), b.get("port_number")),
                                                      f"{b.get('adapter_number')}/{b.get('port_number')}")
        out.append((na.get("name"), pa, nb.get("name"), pb))
    return out

# ------------------------------ Tools ------------------------------------

@mcp.tool()
async def get_projects(server: str, user: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    """List all GNS3 projects on a server.

    Args:
        server: Base URL of the GNS3 server, e.g. "http://127.0.0.1:3080".
        user: Optional HTTP Basic username.
        password: Optional HTTP Basic password.

    Returns:
        {"projects": [...]} where each item is a project dict from /v2/projects.

    Example:
        "List projects on http://172.16.194.129:80"
    """
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=30.0) as c:
        return {"projects": await _projects(c, base)}

@mcp.tool()
async def get_project(server: str,
                      name: Optional[str] = None,
                      project_id: Optional[str] = None,
                      user: Optional[str] = None,
                      password: Optional[str] = None) -> Dict[str, Any]:
    """Fetch a single project by name or ID.

    You must provide exactly one of (name, project_id).

    Args:
        server: GNS3 base URL, e.g. "http://127.0.0.1:3080".
        name: Project name to search for (exact match).
        project_id: Project UUID.
        user, password: Optional HTTP Basic auth.

    Returns:
        Project dict from /v2/projects/{id} (or the match by name).

    Example:
        "Get the project named test-gns3-api on http://172.16.194.129:80"
    """
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=30.0) as c:
        return await _project_by_name_or_id(c, base, name=name, project_id=project_id)

@mcp.tool()
async def get_templates(server: str, user: Optional[str] = None, password: Optional[str] = None) -> Dict[str, str]:
    """List templates as {name -> template_id}.

    Args:
        server: GNS3 base URL.
        user, password: Optional HTTP Basic auth.

    Returns:
        Mapping from template name to template_id.

    Example:
        "Show templates on http://172.16.194.129:80"
    """
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=30.0) as c:
        t = await _templates(c, base)
        return {x.get("name"): x.get("template_id") for x in t}

@mcp.tool()
async def get_template(server: str,
                       name: Optional[str] = None,
                       template_id: Optional[str] = None,
                       user: Optional[str] = None,
                       password: Optional[str] = None) -> Dict[str, Any]:
    """Fetch a single template by name or ID.

    You must provide exactly one of (name, template_id).

    Args:
        server: GNS3 base URL.
        name: Template name (exact).
        template_id: Template UUID.
        user, password: Optional HTTP Basic auth.

    Returns:
        Template dict from /v2/templates/{id}.
    """
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=30.0) as c:
        return await _template_by_name_or_id(c, base, name=name, template_id=template_id)

@mcp.tool()
async def get_nodes(server: str, project_id: str,
                    user: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    """List all nodes in a project.

    Args:
        server: GNS3 base URL.
        project_id: Project UUID.
        user, password: Optional HTTP Basic auth.

    Returns:
        {"nodes": [...]} where each item is a node dict from /v2/projects/{id}/nodes.

    Example:
        "List nodes for project <PROJECT_ID> on http://172.16.194.129:80"
    """
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=30.0) as c:
        return {"nodes": await _nodes(c, base, project_id)}

@mcp.tool()
async def get_node(server: str, project_id: str, node_id: str,
                   user: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    """Fetch a single node by ID.

    Args:
        server: GNS3 base URL.
        project_id: Project UUID.
        node_id: Node UUID.
        user, password: Optional HTTP Basic auth.

    Returns:
        Node dict from /v2/projects/{project_id}/nodes/{node_id}.
    """
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=30.0) as c:
        return await _node(c, base, project_id, node_id)

@mcp.tool()
async def get_links(server: str, project_id: str,
                    user: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    """List all links in a project.

    Args:
        server: GNS3 base URL.
        project_id: Project UUID.
        user, password: Optional HTTP Basic auth.

    Returns:
        {"links": [...]} where each item is a link dict from /v2/projects/{id}/links.
    """
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=30.0) as c:
        return {"links": await _links(c, base, project_id)}

@mcp.tool()
async def get_link(server: str, project_id: str, link_id: str,
                   user: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    """Fetch a single link by ID.

    Args:
        server: GNS3 base URL.
        project_id: Project UUID.
        link_id: Link UUID.
        user, password: Optional HTTP Basic auth.

    Returns:
        Link dict from /v2/projects/{project_id}/links/{link_id}.
    """
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=30.0) as c:
        return await _link(c, base, project_id, link_id)

@mcp.tool()
async def start_node(server: str, project_id: str, node_id: str,
                     user: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    """Start a node.

    POST /v2/projects/{project_id}/nodes/{node_id}/start

    Args:
        server: GNS3 base URL.
        project_id: Project UUID.
        node_id: Node UUID.
        user, password: Optional HTTP Basic auth.

    Returns:
        Result dict from the server (often includes updated node status).
    """
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=60.0) as c:
        return await _node_action(c, base, project_id, node_id, "start")

@mcp.tool()
async def stop_node(server: str, project_id: str, node_id: str,
                    user: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    """Stop a node.

    POST /v2/projects/{project_id}/nodes/{node_id}/stop
    """
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=60.0) as c:
        return await _node_action(c, base, project_id, node_id, "stop")

@mcp.tool()
async def reload_node(server: str, project_id: str, node_id: str,
                      user: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    """Reload a node.

    POST /v2/projects/{project_id}/nodes/{node_id}/reload
    """
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=60.0) as c:
        return await _node_action(c, base, project_id, node_id, "reload")

@mcp.tool()
async def suspend_node(server: str, project_id: str, node_id: str,
                       user: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    """Suspend a node.

    POST /v2/projects/{project_id}/nodes/{node_id}/suspend
    """
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=60.0) as c:
        return await _node_action(c, base, project_id, node_id, "suspend")

@mcp.tool()
async def start_all_nodes(server: str, project_id: str,
                          user: Optional[str] = None, password: Optional[str] = None) -> str:
    """Start all nodes in a project.

    POST /v2/projects/{project_id}/nodes/start

    Returns:
        "OK" on success.
    """
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=120.0) as c:
        await _project_nodes_action(c, base, project_id, "start")
        return "OK"

@mcp.tool()
async def stop_all_nodes(server: str, project_id: str,
                         user: Optional[str] = None, password: Optional[str] = None) -> str:
    """Stop all nodes in a project.

    POST /v2/projects/{project_id}/nodes/stop

    Returns:
        "OK" on success.
    """
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=120.0) as c:
        await _project_nodes_action(c, base, project_id, "stop")
        return "OK"

@mcp.tool()
async def node_summary(server: str, project_id: str,
                       user: Optional[str] = None, password: Optional[str] = None
                       ) -> List[Tuple[str, str, Optional[int], str]]:
    """Return node summary tuples for a project.

    Format:
        (name, status, console_port, node_id)

    Args:
        server: GNS3 base URL.
        project_id: Project UUID.

    Example:
        "Summarize nodes (name, status, console, id) for <PROJECT_ID> on http://..."
    """
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=30.0) as c:
        return _nodes_summary(await _nodes(c, base, project_id))

@mcp.tool()
async def node_inventory(server: str, project_id: str,
                         user: Optional[str] = None, password: Optional[str] = None
                         ) -> Dict[str, dict]:
    """Return an inventory dict keyed by node name.

    Each value includes: server, name, console_port, console_type, type, template.

    Args:
        server: GNS3 base URL.
        project_id: Project UUID.
    """
    base = _base(server)
    # cheap host parse; avoids extra deps
    try:
        server_host = server.split("://", 1)[1].split("/", 1)[0].split(":")[0]
    except Exception:
        server_host = "unknown"
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=30.0) as c:
        nodes = await _nodes(c, base, project_id)
        return _nodes_inventory(server_host, nodes)

@mcp.tool()
async def link_summary(server: str, project_id: str,
                       user: Optional[str] = None, password: Optional[str] = None
                       ) -> List[Tuple[str, str, str, str]]:
    """Return link summary tuples for a project.

    Format:
        (node_a, port_name_a, node_b, port_name_b)

    Args:
        server: GNS3 base URL.
        project_id: Project UUID.
    """
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=30.0) as c:
        nodes = await _nodes(c, base, project_id)
        links = await _links(c, base, project_id)
        return _links_summary(nodes, links)

# -------------------- Topology building helpers (NEW) --------------------

@mcp.tool()
async def create_node_from_template(
    server: str,
    project_id: str,
    template: Optional[str] = None,
    template_id: Optional[str] = None,
    name: Optional[str] = None,
    x: int = 0,
    y: int = 0,
    compute_id: str = "local",
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a single node from a template and place it at (x, y).

    You must provide exactly one of (template, template_id).

    Args:
        server: GNS3 base URL.
        project_id: Project UUID.
        template: Template name (exact), e.g. "Ethernet switch".
        template_id: Template UUID (if you already know it).
        name: Optional node name override (server will assign default if omitted).
        x, y: Canvas coordinates.
        compute_id: Target compute; defaults to "local".
        user, password: Optional HTTP Basic auth.

    Returns:
        Created node dict from POST /v2/projects/{project_id}/templates/{template_id}.

    Notes:
        - If only `template` is provided, the server will look up its template_id first.
        - After creation, you can reposition with PUT /nodes/{node_id} if needed.

    Example:
        "Create a node from the 'Ethernet switch' template named Core-SW at (200,100) in <PROJECT_ID>"
    """
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=60.0) as c:
        if not template_id:
            if not template:
                raise ValueError("Provide either template or template_id")
            t = await _template_by_name_or_id(c, base, name=template, template_id=None)
            template_id = t["template_id"]

        payload = {"compute_id": compute_id, "x": x, "y": y}
        if name:
            payload["name"] = name

        node = await _apost(c, f"{base}/projects/{project_id}/templates/{template_id}", json=payload)
        return node

@mcp.tool()
async def link_nodes(
    server: str,
    project_id: str,
    # Form A: by node names + port names (recommended for humans)
    node_a_name: Optional[str] = None,
    port_a_name: Optional[str] = None,
    node_b_name: Optional[str] = None,
    port_b_name: Optional[str] = None,
    # Form B: by node IDs + adapter/port numbers (for programmatic callers)
    node_a_id: Optional[str] = None,
    a_adapter: Optional[int] = None,
    a_port: Optional[int] = None,
    node_b_id: Optional[str] = None,
    b_adapter: Optional[int] = None,
    b_port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a link between two nodes.

    Choose ONE form:

    Form A (friendly): identify endpoints by node name + port name
        - node_a_name, port_a_name, node_b_name, port_b_name
        - Port name must match the node's port 'name' attribute.

    Form B (explicit): identify endpoints by node_id + adapter_number/port_number
        - node_a_id, a_adapter, a_port, node_b_id, b_adapter, b_port

    Args:
        server: GNS3 base URL.
        project_id: Project UUID.
        user, password: Optional HTTP Basic auth.

    Returns:
        Link dict from POST /v2/projects/{project_id}/links.

    Examples:
        A) "Link 'FW-1' Gi0/0 to 'SW-1' Ethernet1 in <PROJECT_ID>"
        B) "Link node A (id=...) adapter 0/port 0 to node B (id=...) adapter 0/port 1"

    Notes:
        - This mirrors the legacy behavior: we resolve names to IDs and port numbers
          when Form A is used, and we detect busy ports when possible.
    """
    base = _base(server)
    async with httpx.AsyncClient(auth=_auth(user, password), timeout=60.0) as c:
        # Resolve Form A (names) if provided
        def _by_name(nodes: List[dict], n: str) -> dict:
            for x in nodes:
                if x.get("name") == n:
                    return x
            raise ValueError(f"Node not found by name: {n}")

        if node_a_name or node_b_name:
            if not (node_a_name and port_a_name and node_b_name and port_b_name):
                raise ValueError("Form A requires node_a_name, port_a_name, node_b_name, port_b_name")
            nodes = await _nodes(c, base, project_id)
            a = _by_name(nodes, node_a_name)
            b = _by_name(nodes, node_b_name)

            def _port_lookup(node: dict, wanted: str) -> tuple[int, int]:
                for p in node.get("ports", []) or []:
                    if p.get("name") == wanted:
                        return int(p.get("adapter_number")), int(p.get("port_number"))
                raise ValueError(f"Port name not found on {node.get('name')}: {wanted}")

            a_adapter, a_port = _port_lookup(a, port_a_name)
            b_adapter, b_port = _port_lookup(b, port_b_name)
            node_a_id, node_b_id = a["node_id"], b["node_id"]

        # Validate Form B fields
        if not (node_a_id and node_b_id and a_adapter is not None and a_port is not None and
                b_adapter is not None and b_port is not None):
            raise ValueError("Provide either Form A (names) OR Form B (ids+adapter/port).")

        payload = {
            "nodes": [
                {"node_id": node_a_id, "adapter_number": int(a_adapter), "port_number": int(a_port)},
                {"node_id": node_b_id, "adapter_number": int(b_adapter), "port_number": int(b_port)},
            ]
        }
        return await _apost(c, f"{base}/projects/{project_id}/links", json=payload)

# ------------------------------ Entrypoint --------------------------------

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
