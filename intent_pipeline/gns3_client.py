"""Minimal GNS3 REST client used for inventory collection and command dispatch."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

from .config import GNS3Config


@dataclass
class GNS3Node:
    node_id: str
    name: str
    node_type: str
    console_host: Optional[str]
    console_port: Optional[int]
    status: str
    properties: Dict[str, Any]


class GNS3Client:
    def __init__(self, config: GNS3Config) -> None:
        self._cfg = config
        self._session = requests.Session()
        if config.username and config.password:
            self._session.auth = (config.username, config.password)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self._cfg.base_url}{path}"
        resp = self._session.request(method, url, timeout=30, **kwargs)
        if resp.status_code >= 400:
            raise RuntimeError(f"GNS3 API {method} {path} failed: {resp.status_code} {resp.text}")
        if resp.content:
            return resp.json()
        return None

    def list_projects(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/projects")

    def get_project_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        for project in self.list_projects():
            if project.get("name") == name:
                return project
        return None

    def get_project_nodes(self, project_id: str) -> List[GNS3Node]:
        data = self._request("GET", f"/projects/{project_id}/nodes")
        nodes: List[GNS3Node] = []
        for item in data:
            nodes.append(
                GNS3Node(
                    node_id=item.get("node_id", ""),
                    name=item.get("name", ""),
                    node_type=item.get("node_type", ""),
                    console_host=item.get("console_host"),
                    console_port=item.get("console_port"),
                    status=item.get("status", "unknown"),
                    properties=item.get("properties", {}),
                )
            )
        return nodes

    def get_node_detail(self, project_id: str, node_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/projects/{project_id}/nodes/{node_id}")

    def get_node_interfaces(self, project_id: str, node_id: str) -> List[Dict[str, Any]]:
        try:
            detail = self.get_node_detail(project_id, node_id)
        except RuntimeError as exc:
            if "404" in str(exc):
                return []
            raise
        ports = detail.get("ports") or detail.get("interfaces") or []
        return ports

    def get_links(self, project_id: str) -> List[Dict[str, Any]]:
        return self._request("GET", f"/projects/{project_id}/links")
