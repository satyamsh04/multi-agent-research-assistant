"""Agent execution backends.

A single :func:`run_agent` entry point hides the choice of backend:

* **OpenClaw** — used when the ``openclaw_sdk`` package is importable *and* the
  local gateway is reachable. The agent persona is bootstrapped from its
  SOUL/SKILL files on the gateway side.
* **OpenAI** — transparent fallback that injects the same SOUL + SKILL content
  as a system prompt, so the persona is identical across backends.

Both paths return an :class:`AgentResult` with the same shape, so callers never
branch on the backend.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from .agents import load_agent_prompt
from .config import OPENAI_TIMEOUT_S, Settings


@dataclass
class AgentResult:
    success: bool
    content: str
    latency_ms: int
    backend: str  # "openclaw" or "openai"


class BackendError(RuntimeError):
    """Raised when no backend can fulfil an agent turn."""


def _openclaw_available() -> bool:
    try:
        import openclaw_sdk  # noqa: F401
    except Exception:
        return False
    return True


async def _execute_openclaw(agent_id: str, prompt: str) -> AgentResult:
    """Run a single agent turn through the local OpenClaw gateway."""
    from openclaw_sdk import OpenClawClient  # type: ignore

    started = time.perf_counter()
    async with OpenClawClient.connect() as client:
        agent = client.get_agent(agent_id)
        result = await agent.execute(prompt)

    latency = getattr(result, "latency_ms", None)
    if not latency:
        latency = int((time.perf_counter() - started) * 1000)
    content = str(getattr(result, "content", "") or "")
    return AgentResult(
        success=bool(getattr(result, "success", True)) and bool(content),
        content=content,
        latency_ms=int(latency),
        backend="openclaw",
    )


def _execute_openai(agent_id: str, prompt: str, settings: Settings) -> AgentResult:
    """Run a single agent turn through OpenAI's Chat Completions API."""
    from openai import OpenAI

    if not settings.has_openai:
        raise BackendError(
            "OpenAI API key is not set and the OpenClaw gateway is unavailable. "
            "Set OPENAI_API_KEY in your .env or start the local OpenClaw gateway."
        )

    system_prompt = load_agent_prompt(agent_id)
    client = OpenAI(api_key=settings.openai_api_key, timeout=OPENAI_TIMEOUT_S)
    started = time.perf_counter()
    completion = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    content = (completion.choices[0].message.content or "").strip()
    return AgentResult(
        success=bool(content),
        content=content,
        latency_ms=elapsed_ms,
        backend="openai",
    )


def run_agent(agent_id: str, prompt: str, settings: Settings) -> AgentResult:
    """Execute one agent turn, preferring OpenClaw and falling back to OpenAI.

    Raises :class:`BackendError` only if *no* backend can run the turn.
    """
    if _openclaw_available():
        try:
            result = asyncio.run(_execute_openclaw(agent_id, prompt))
            if result.success and result.content:
                return result
        except Exception:
            # Gateway present but unhealthy: fall through to OpenAI rather than
            # failing the whole run.
            pass

    return _execute_openai(agent_id, prompt, settings)
