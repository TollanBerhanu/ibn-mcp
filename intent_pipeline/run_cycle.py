"""Command line entrypoint for the IBN demo pipeline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from .config import load_gns3_config, load_paths
from .intent_activation import activate_policy
from .intent_assurance import assure_policy
from .intent_resolver import resolve_policy
from .intent_translator import translate_intent
from .inventory import build_inventory
from .policy_store import PolicyStore
from .topology import load_topology


def _load_inventory(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise RuntimeError("Inventory file not found; run with --refresh-inventory")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the IBN demo pipeline")
    parser.add_argument("--intent", help="Natural language intent to translate")
    parser.add_argument("--policy-id", help="Existing policy to operate on")
    parser.add_argument(
        "--refresh-inventory",
        action="store_true",
        help="Refresh inventory from GNS3 before running",
    )
    parser.add_argument(
        "--skip-activation",
        action="store_true",
        help="Stop after resolution",
    )
    parser.add_argument(
        "--skip-assurance",
        action="store_true",
        help="Stop after activation",
    )
    args = parser.parse_args(argv)

    paths = load_paths()
    gns3_cfg = load_gns3_config()
    topology = load_topology(paths.topology)
    store = PolicyStore(paths.policy_store)

    if args.refresh_inventory or not paths.inventory.exists():
        print("[inventory] collecting data from GNS3 ...")
        build_inventory(paths, gns3_cfg, topology)
        print("[inventory] saved to", paths.inventory)

    inventory = _load_inventory(paths.inventory)

    policy_id = args.policy_id
    if args.intent:
        print("[translate] creating policy from intent ...")
        policy = translate_intent(args.intent, topology, inventory, paths, store)
        policy_id = policy["policy_id"]
        print(f"[translate] policy stored as {policy_id}")
    elif not policy_id:
        if args.refresh_inventory:
            print("[run] inventory refreshed; no policy actions requested")
            return
        raise RuntimeError("Provide either --intent or --policy-id")

    print("[resolve] checking policy feasibility ...")
    policy = resolve_policy(policy_id, store, inventory, topology)
    resolution_state = policy.get("status", {}).get("resolution")
    print(f"[resolve] status: {resolution_state}")
    if resolution_state != "completed":
        print("[resolve] issues:")
        for line in policy.get("status", {}).get("resolution_details", []):
            print(f"  - {line}")
        return

    if args.skip_activation:
        print("[skip] activation disabled by flag")
        return

    print("[activate] applying policy commands ...")
    policy = activate_policy(policy_id, store, inventory, gns3_cfg)
    activation_state = policy.get("status", {}).get("activation")
    print(f"[activate] status: {activation_state}")
    if activation_state != "completed":
        for line in policy.get("status", {}).get("activation_details", []):
            print(f"  - {line}")
        return

    if args.skip_assurance:
        print("[skip] assurance disabled by flag")
        return

    print("[assure] running validation checks ...")
    policy = assure_policy(policy_id, store, inventory, gns3_cfg)
    assurance_state = policy.get("status", {}).get("assurance")
    print(f"[assure] status: {assurance_state}")
    if assurance_state != "completed":
        for line in policy.get("status", {}).get("assurance_details", []):
            print(f"  - {line}")
    else:
        print("[assure] policy satisfied")


if __name__ == "__main__":
    main()
