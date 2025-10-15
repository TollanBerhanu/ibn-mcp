"""Apply network policies over telnet sessions."""
from __future__ import annotations

from typing import Any, Dict, List

from .config import GNS3Config
from .policy_store import PolicyStore
from .telnet_executor import TelnetExecutor


def activate_policy(
    policy_id: str,
    store: PolicyStore,
    inventory: Dict[str, Any],
    gns3_cfg: GNS3Config,
) -> Dict[str, Any]:
    policy = store.get_policy(policy_id)
    if not policy:
        raise KeyError(f"Policy {policy_id} not found")

    nodes = {node.get("name"): node for node in inventory.get("nodes", [])}
    transcripts: List[Dict[str, Any]] = []
    errors: List[str] = []

    for step in policy.get("enforcement_steps", []):
        device = step.get("device")
        node = nodes.get(device or "")
        if not node:
            errors.append(f"Device '{device}' missing from inventory")
            continue

        host = node.get("console_host") or gns3_cfg.host
        if host in ("0.0.0.0", "127.0.0.1", ""):
            host = gns3_cfg.host
        port = node.get("console_port")
        if not port:
            errors.append(f"Device '{device}' missing console port info")
            continue

        commands = step.get("commands", [])
        if not commands:
            continue

        try:
            with TelnetExecutor(host, int(port)) as session:
                output = session.run_commands(commands)
                transcripts.append(
                    {
                        "device": device,
                        "commands": commands,
                        "output": output,
                    }
                )
        except Exception as exc:  # noqa: PIE786
            errors.append(f"Failed to run commands on {device}: {exc}")

    status = policy.setdefault("status", {})
    if errors:
        status["activation"] = "failed"
        status["activation_details"] = errors
    else:
        status["activation"] = "completed"
        status["activation_details"] = ["Commands executed on all targets"]

    policy["activation_logs"] = transcripts
    updated = {**policy, "status": status}
    store.upsert_policy(updated)
    return updated
