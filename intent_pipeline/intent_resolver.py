"""Basic feasibility checks for policies before activation."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from .policy_store import PolicyStore
from .topology import TopologyContext


def _normalize(value: str) -> str:
    return value.strip().lower()


def _known_subnet_tokens(topology: Optional[TopologyContext]) -> Set[str]:
    tokens: Set[str] = set()
    if not topology:
        return tokens
    for subnet in topology.subnets:
        name = subnet.get("name") if isinstance(subnet, dict) else None
        cidr = subnet.get("cidr") if isinstance(subnet, dict) else None
        candidates = [name, cidr]
        if name and cidr:
            candidates.extend(
                [
                    f"{name} ({cidr})",
                    f"{name}:{cidr}",
                    f"subnet:{name}",
                    f"subnet:{cidr}",
                ]
            )
        for item in candidates:
            if item:
                tokens.add(_normalize(item))
    for group in topology.groups:
        group_name = group.get("name") if isinstance(group, dict) else None
        if group_name:
            tokens.add(_normalize(group_name))
            tokens.add(_normalize(f"group:{group_name}"))
    return tokens


def resolve_policy(
    policy_id: str,
    store: PolicyStore,
    inventory: Dict[str, Any],
    topology: Optional[TopologyContext] = None,
) -> Dict[str, Any]:
    policy = store.get_policy(policy_id)
    if not policy:
        raise KeyError(f"Policy {policy_id} not found")

    node_names = {node.get("name") for node in inventory.get("nodes", [])}
    normalized_node_names = {_normalize(name) for name in node_names if name}
    subnet_tokens = _known_subnet_tokens(topology)
    issues: List[str] = []

    for rule in policy.get("policy_rules", []):
        for target in rule.get("targets", []):
            if not target:
                continue
            normalized = _normalize(target)
            if normalized in normalized_node_names or normalized in subnet_tokens:
                continue
            if ":" in target:
                suffix = target.split(":", 1)[1]
                if _normalize(suffix) in normalized_node_names or _normalize(suffix) in subnet_tokens:
                    continue
            issues.append(f"Unknown target '{target}' referenced by rule {rule.get('rule_id')}")

    for step in policy.get("enforcement_steps", []):
        device = step.get("device")
        if device and device not in node_names:
            issues.append(f"Enforcement step references missing node '{device}'")
        if not step.get("commands"):
            issues.append(f"Enforcement step {step.get('step')} has no commands")

    for check in policy.get("validation_checks", []):
        source = check.get("source_device")
        if source and source not in node_names:
            issues.append(
                f"Validation check {check.get('check_id')} references missing node '{source}'"
            )
        if not check.get("commands"):
            issues.append(f"Validation check {check.get('check_id')} has no commands")

    status = policy.setdefault("status", {})
    if issues:
        status["resolution"] = "failed"
        status["resolution_details"] = issues
    else:
        status["resolution"] = "completed"
        status["resolution_details"] = ["All targets validated against current inventory."]

    updated = {**policy, "status": status}
    store.upsert_policy(updated)
    return updated
