"""Very small telnet helper for sending command batches."""
from __future__ import annotations

import telnetlib
import time
from typing import Iterable, List


class TelnetExecutor:
    def __init__(self, host: str, port: int, timeout: int = 10) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._session = telnetlib.Telnet(host, port, timeout)
        self._flush_prompt()

    def _flush_prompt(self) -> None:
        self._session.write(b"\r\n")
        time.sleep(0.2)
        self._session.read_very_eager()

    def _collect_output(self) -> str:
        buffer = b""
        idle_cycles = 0
        deadline = time.time() + self._timeout
        while time.time() < deadline:
            time.sleep(0.2)
            chunk = self._session.read_very_eager()
            if chunk:
                buffer += chunk
                idle_cycles = 0
            else:
                idle_cycles += 1
                if buffer and idle_cycles >= 3:
                    break
        return buffer.decode("utf-8", errors="ignore").strip()

    def run_commands(self, commands: Iterable[str]) -> List[str]:
        outputs: List[str] = []
        for command in commands:
            self._session.write(command.encode("ascii", errors="ignore") + b"\r\n")
            outputs.append(self._collect_output())
        return outputs

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "TelnetExecutor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
