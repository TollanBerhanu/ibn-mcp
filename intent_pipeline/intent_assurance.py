"""Policy assurance by replaying validation checks."""
from __future__ import annotations

from typing import Any, Dict, List

from .config import GNS3Config
from .policy_store import PolicyStore
from .telnet_executor import TelnetExecutor


def assure_policy(
    policy_id: str,
    store: PolicyStore,
    inventory: Dict[str, Any],
    gns3_cfg: GNS3Config,
) -> Dict[str, Any]:
    policy = store.get_policy(policy_id)
    if not policy:
        raise KeyError(f"Policy {policy_id} not found")

    nodes = {node.get("name"): node for node in inventory.get("nodes", [])}
    results: List[Dict[str, Any]] = []
    failures: List[str] = []

    for check in policy.get("validation_checks", []):
        source_device = check.get("source_device")
        node = nodes.get(source_device or "")
        if not node:
            failures.append(
                f"Validation check {check.get('check_id')} cannot find device '{source_device}'"
            )
            continue

        host = node.get("console_host") or gns3_cfg.host
        if host in ("0.0.0.0", "127.0.0.1", ""):
            host = gns3_cfg.host
        port = node.get("console_port")
        commands = check.get("commands", [])
        if not port or not commands:
            failures.append(f"Validation check {check.get('check_id')} missing port/commands")
            continue

        try:
            with TelnetExecutor(host, int(port)) as session:
                output_chunks = session.run_commands(commands)
        except Exception as exc:  # noqa: PIE786
            failures.append(f"Validation check {check.get('check_id')} failed: {exc}")
            continue

        output_text = "\n".join(output_chunks)
        criteria = check.get("success_criteria", "").strip()
        passed = bool(criteria and criteria in output_text) if criteria else bool(output_text)
        if not passed:
            failures.append(
                f"Validation check {check.get('check_id')} did not meet criteria '{criteria}'"
            )

        results.append(
            {
                "check_id": check.get("check_id"),
                "source_device": source_device,
                "commands": commands,
                "output": output_chunks,
                "success": passed,
                "criteria": criteria,
            }
        )

    status = policy.setdefault("status", {})
    if failures:
        status["assurance"] = "failed"
        status["assurance_details"] = failures
    else:
        status["assurance"] = "completed"
        status["assurance_details"] = ["All validation checks passed"]

    policy["assurance_results"] = results
    updated = {**policy, "status": status}
    store.upsert_policy(updated)
    return updated
