"""Inventory collection helpers for the IBN demo."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any, Dict, List

from .config import GNS3Config, Paths
from .gns3_client import GNS3Client, GNS3Node
from .topology import TopologyContext


def build_inventory(
    paths: Paths,
    gns3_cfg: GNS3Config,
    topology: TopologyContext,
    output_path: Path | None = None,
) -> Dict[str, Any]:
    client = GNS3Client(gns3_cfg)
    project = client.get_project_by_name(topology.name)
    if not project:
        raise RuntimeError(f"Project '{topology.name}' not found on the GNS3 server")

    project_id = project["project_id"]
    nodes = client.get_project_nodes(project_id)
    links = client.get_links(project_id)

    inventory_nodes: List[Dict[str, Any]] = []
    for node in nodes:
        detail: Dict[str, Any] = {}
        try:
            detail = client.get_node_detail(project_id, node.node_id)
        except RuntimeError as exc:  # noqa: PIE786
            detail = {"error": str(exc)}
            interfaces: List[Dict[str, Any]] = []
        else:
            interfaces = detail.get("ports") or detail.get("interfaces") or []

        node_entry = asdict(node)
        if not node_entry.get("console_host"):
            node_entry["console_host"] = detail.get("console_host") or gns3_cfg.host
        if not node_entry.get("console_port"):
            node_entry["console_port"] = detail.get("console")

        inventory_nodes.append(
            {
                **node_entry,
                "interfaces": interfaces,
                "detail": detail,
            }
        )

    inventory = {
        "topology_name": topology.name,
        "project_id": project_id,
        "project_path": project.get("project_path"),
        "nodes": inventory_nodes,
        "links": links,
    }

    target = output_path or paths.inventory
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    return inventory
