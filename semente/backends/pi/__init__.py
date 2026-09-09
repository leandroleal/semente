"""pi backend — Earendil pi coding agent via RPC sidecar.

pi is a Node/TypeScript runtime with no Python SDK. This backend spawns
``pi --mode rpc`` and speaks its JSONL protocol over stdio. Custom tools are
TypeScript extensions in pi, so domain tools are proxied through a generated
bridge extension + a Semente tool server (see MULTI_ENGINE.md §4.3).

Status: experimental. The RPC prompt/response loop is implemented; the tool
bridge is the spike-gated follow-up.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
from typing import Any

from semente.backends.base import Agent, AgentInput, AgentSpec, AgentTurn, EngineBackend


class _PiRpcClient:
    """Minimal pi RPC client: JSONL commands over stdin, events over stdout."""

    def __init__(self, provider: str | None = None, model: str | None = None):
        cmd = ["pi", "--mode", "rpc", "--no-session"]
        if provider:
            cmd += ["--provider", provider]
        if model:
            cmd += ["--model", model]
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._lock = threading.Lock()
        self._req_id = 0

    def _next_id(self) -> str:
        self._req_id += 1
        return f"req-{self._req_id}"

    def prompt(self, message: str, images: list[bytes] | None = None) -> str:
        """Send a prompt and collect the final assistant text."""
        with self._lock:
            req_id = self._next_id()
            cmd: dict[str, Any] = {"id": req_id, "type": "prompt", "message": message}
            if images:
                import base64

                cmd["images"] = [
                    {"type": "image", "data": base64.b64encode(b).decode(), "mimeType": "image/png"}
                    for b in images
                ]
            self.proc.stdin.write(json.dumps(cmd) + "\n")
            self.proc.stdin.flush()

            final_text = ""
            # Read events until turn_end. Strict LF framing (pi docs: do not
            # use readline — it splits on U+2028/2029).
            for line in self.proc.stdout:
                line = line.strip("\r\n")
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "turn_end":
                    msg = event.get("message") or {}
                    parts = msg.get("content") or []
                    final_text = "".join(
                        p.get("text", "") for p in parts if isinstance(p, dict) and p.get("type") == "text"
                    )
                    break
            return final_text

    def close(self):
        try:
            self.proc.terminate()
        except Exception:
            pass


class PiAgentAdapter:
    def __init__(self, client: _PiRpcClient):
        self.client = client

    def run(self, input: AgentInput) -> AgentTurn:
        text = self.client.prompt(input.text, images=input.images)
        return AgentTurn(content=text)


class PiBackend(EngineBackend):
    name = "pi"

    def build_agent(self, spec: AgentSpec) -> Agent:
        provider = spec.model.provider if spec.model else None
        model_id = spec.model.model_id if spec.model else None
        client = _PiRpcClient(provider=provider, model=model_id)
        return PiAgentAdapter(client)

    def supports(self, capability: str) -> bool:
        return capability in {"multimodal_in"}
