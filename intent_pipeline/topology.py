"""Helpers for working with the static topology definition."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import yaml


@dataclass
class TopologyContext:
    name: str
    description: str
    subnets: List[Dict[str, Any]]
    nodes: List[Dict[str, Any]]
    groups: List[Dict[str, Any]]


def load_topology(path: Path) -> TopologyContext:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not data:
        raise RuntimeError(f"Topology file {path} is empty")
    return TopologyContext(
        name=data.get("topology", ""),
        description=data.get("description", ""),
        subnets=data.get("subnets", []),
        nodes=data.get("nodes", []),
        groups=data.get("groups", []),
    )
