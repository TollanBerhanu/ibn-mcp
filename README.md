# Intent-Based Networking Demo

This project is a lightweight intent-based networking (IBN) workflow tailored for a GNS3 lab. It focuses on clarity over scale: a single CLI walks an intent through translation, feasibility checks, activation via telnet, and assurance testing.

## What the pipeline does

- **Inventory capture** – talks to the GNS3 REST API to cache node IDs, console ports, and links for the current topology.
- **Intent translation** – sends the natural-language goal and topology context to OpenAI, producing a structured policy entry.
- **Intent resolution** – validates that the policy only references available devices and that each step/test is actionable.
- **Intent activation** – connects to GNS3 node consoles over telnet and executes the enforcement commands listed in the policy.
- **Intent assurance** – reuses telnet sessions to run validation commands and checks outputs against success criteria.

Every stage appends its results to the YAML policy store so you can review or tweak the policy between runs.

## Getting started

1. **Install dependencies** (uses `uv`, but pip works too):
   ```bash
   uv sync
   ```

2. **Configure credentials** in `.env` (already present in this repo):
   ```ini
   OPENAI_API_KEY=...
   OPENAI_MODEL=gpt-5
   GNS3_SERVER_IP=...
   GNS3_SERVER_PORT=...
   GNS3_SERVER_USER=...
   GNS3_SERVER_PASSWORD=...
   ```

3. **Collect inventory** from the running GNS3 project:
   ```bash
   uv run python -m intent_pipeline.run_cycle --refresh-inventory
   ```
   This writes `inventory/gns3_inventory.json`. Re-run with an intent afterward.

## Running an intent end to end

```bash
uv run python -m intent_pipeline.run_cycle --intent "Block east LAN from west LAN"
```

The CLI prints progress for each stage:

1. **translate** – generates `policies/ibn_policies.yaml` entry.
2. **resolve** – fails fast if devices are missing or if commands/tests are empty.
3. **activate** – pushes telnet commands; logs captured output in the policy entry.
4. **assure** – replays validation checks; marks the policy as satisfied or explains failures.

Flags:

- `--policy-id` – operate on an existing policy without re-translating.
- `--refresh-inventory` – rebuild cached inventory before running.
- `--skip-activation` / `--skip-assurance` – stop after the previous stage.

## Files of interest

- `topology.yaml` – static, human-authored topology context.
- `inventory/gns3_inventory.json` – cached details from the GNS3 API.
- `policies/ibn_policies.yaml` – accumulated policies with stage status, logs, and test results.
- `intent_pipeline/` – Python modules for each stage.

## Telnet notes

The telnet helper sends newline-separated commands and collects eager output. It assumes prompts ending with `#`, `>`, or `$`; adjust `intent_pipeline/telnet_executor.py` if your node shells differ. If a device exposes its console on `0.0.0.0`, the CLI falls back to the configured GNS3 host.

## Development tips

- Policies are plain YAML—edit them manually if you want to fine-tune commands before activation.
- The resolver is intentionally simple; add custom checks in `intent_pipeline/intent_resolver.py` if needed.
- Run individual stages by calling the underlying functions in a Python REPL for quicker iteration.

## License

Add the license text that fits your course or project submission.
