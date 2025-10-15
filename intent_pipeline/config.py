"""Configuration helpers for the IBN demo."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


load_dotenv()


@dataclass
class OpenAIConfig:
    api_key: str
    model: str


@dataclass
class GNS3Config:
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/v2"


@dataclass
class Paths:
    root: Path
    topology: Path
    policy_store: Path
    inventory: Path


def load_openai_config() -> OpenAIConfig:
    api_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return OpenAIConfig(api_key=api_key, model=model)


def load_gns3_config() -> GNS3Config:
    host = os.environ.get("GNS3_SERVER_IP")
    port = int(os.environ.get("GNS3_SERVER_PORT", "80"))
    if not host:
        raise RuntimeError("GNS3_SERVER_IP is not configured")
    return GNS3Config(
        host=host,
        port=port,
        username=os.environ.get("GNS3_SERVER_USER"),
        password=os.environ.get("GNS3_SERVER_PASSWORD"),
    )


def load_paths() -> Paths:
    root = Path(__file__).resolve().parents[1]
    return Paths(
        root=root,
        topology=root / "topology.yaml",
        policy_store=root / "policies" / "ibn_policies.yaml",
        inventory=root / "inventory" / "gns3_inventory.json",
    )
