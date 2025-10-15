"""Translate natural-language intents into structured policies using OpenAI."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, cast
from uuid import uuid4

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from .config import Paths, load_openai_config
from .policy_store import PolicyStore
from .topology import TopologyContext

_SYSTEM_PROMPT = (
    "You design human readable and machine actionable network policies. "
    "Always respond with valid JSON that matches the requested schema."
)


def _make_policy_id() -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"policy-{stamp}-{uuid4().hex[:6]}"


def translate_intent(
    intent_text: str,
    topology: TopologyContext,
    inventory: Optional[Dict[str, Any]],
    paths: Paths,
    policy_store: Optional[PolicyStore] = None,
) -> Dict[str, Any]:
    cfg = load_openai_config()
    client = OpenAI(api_key=cfg.api_key)

    node_names = [node.get("name", "") for node in topology.nodes]
    allowed_targets = ", ".join(sorted(name for name in node_names if name))

    context = {
        "topology": {
            "name": topology.name,
            "description": topology.description,
            "nodes": topology.nodes,
            "subnets": topology.subnets,
            "groups": topology.groups,
        },
        "inventory": inventory or {},
    }

    user_prompt = (
        "You are given an intent in natural language. "
        "Generate a network policy object as JSON with fields: "
        "policy_id, intent, policy_rules, enforcement_steps, validation_checks, status, notes. "
        "Follow this schema: \n"
        "{\n"
        "  \"policy_id\": str,\n"
        "  \"intent\": {\n"
        "    \"raw\": original string,\n"
        "    \"summary\": short paraphrase,\n"
        "    \"assumptions\": [str]\n"
        "  },\n"
        "  \"policy_rules\": [ {\n"
        "    \"rule_id\": str,\n"
        "    \"description\": str,\n"
        "    \"targets\": [str],\n"
        "    \"action\": str,\n"
        "    \"constraints\": [str]\n"
        "  } ],\n"
        "  \"enforcement_steps\": [ {\n"
        "    \"step\": int,\n"
        "    \"device\": str,\n"
        "    \"method\": \"telnet\" or \"api\",\n"
        "    \"commands\": [str],\n"
        "    \"notes\": str\n"
        "  } ],\n"
    "  \"validation_checks\": [ {\n"
    "    \"check_id\": str,\n"
    "    \"description\": str,\n"
    "    \"type\": str,\n"
    "    \"source_device\": str,\n"
    "    \"commands\": [str],\n"
    "    \"success_criteria\": str\n"
    "  } ],\n"
        "  \"status\": {\n"
        "    \"translation\": \"pending\",\n"
        "    \"resolution\": \"pending\",\n"
        "    \"activation\": \"pending\",\n"
        "    \"assurance\": \"pending\"\n"
        "  },\n"
        "  \"notes\": str\n"
        "}. "
        "Every command should be explicit. Use device names from the topology context."
    )

    if allowed_targets:
        user_prompt += (
            "\nValid device targets: "
            + allowed_targets
            + ". Use only these names in the `targets` array and `device` fields. "
            "Describe subnets, chains, or interfaces within constraints or notes instead of adding them to targets."
        )

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Context:\n"
                + json.dumps(context, indent=2)
                + "\n\n"
                + user_prompt
                + "\n\nIntent:\n"
                + intent_text
            ),
        },
    ]

    completion = client.chat.completions.create(  # type: ignore[attr-defined]
        model=cfg.model,
        messages=cast(List[ChatCompletionMessageParam], messages),
    )

    payload = completion.choices[0].message.content or "{}"
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "OpenAI response was not valid JSON. Received:\n" + payload
        ) from exc

    if not data.get("policy_id"):
        data["policy_id"] = _make_policy_id()

    data.setdefault("status", {})
    for key in ("translation", "resolution", "activation", "assurance"):
        data["status"].setdefault(key, "pending")

    data["status"]["translation"] = "completed"
    data["status"]["last_updated"] = datetime.utcnow().isoformat() + "Z"

    paths.policy_store.parent.mkdir(parents=True, exist_ok=True)
    if not paths.policy_store.exists():
        paths.policy_store.write_text("policies: []\n", encoding="utf-8")

    store = policy_store or PolicyStore(paths.policy_store)
    store.upsert_policy(data)
    return data
