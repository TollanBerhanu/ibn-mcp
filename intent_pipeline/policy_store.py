"""Simple YAML-backed policy store used by the IBN demo."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class PolicyEntry:
    policy_id: str
    intent: Dict[str, Any]
    policy_rules: List[Dict[str, Any]]
    enforcement_steps: List[Dict[str, Any]]
    validation_checks: List[Dict[str, Any]]
    status: Dict[str, Any]
    notes: Optional[str] = None


class PolicyStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("policies: []\n", encoding="utf-8")

    def load(self) -> Dict[str, Any]:
        with self._path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        data.setdefault("policies", [])
        return data

    def save(self, data: Dict[str, Any]) -> None:
        data.setdefault("policies", [])
        with self._path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, sort_keys=False)

    def list_policies(self) -> List[Dict[str, Any]]:
        return list(self.load().get("policies", []))

    def get_policy(self, policy_id: str) -> Optional[Dict[str, Any]]:
        for entry in self.list_policies():
            if entry.get("policy_id") == policy_id:
                return entry
        return None

    def upsert_policy(self, policy: Dict[str, Any]) -> Dict[str, Any]:
        data = self.load()
        policies = data.setdefault("policies", [])
        for idx, entry in enumerate(policies):
            if entry.get("policy_id") == policy.get("policy_id"):
                policies[idx] = policy
                break
        else:
            policies.append(policy)
        self.save(data)
        return policy

    def update_policy(self, policy_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        data = self.load()
        policies = data.setdefault("policies", [])
        for idx, entry in enumerate(policies):
            if entry.get("policy_id") == policy_id:
                merged = {**entry, **patch}
                policies[idx] = merged
                self.save(data)
                return merged
        raise KeyError(f"Policy {policy_id} not found")
