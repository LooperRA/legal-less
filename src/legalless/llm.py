"""Thin, auditable LLM client used by the ratio pipeline.

* OpenAI-compatible Chat Completions (``OPENAI_API_KEY`` / ``OPENAI_API_BASE``).
* Strict JSON-schema responses only; every response is parsed and validated.
* Every call is logged (model, tokens, latency) so a run's cost can be audited.
* The client is injectable: tests pass a fake object exposing ``complete_json``.
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Protocol


class JSONModel(Protocol):
    def complete_json(self, *, system: str, user: str, schema: dict[str, Any], name: str,
                      max_tokens: int = 4000) -> dict[str, Any]: ...


@dataclass
class CallLog:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    failures: int = 0
    seconds: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, usage: Any, seconds: float) -> None:
        with self.lock:
            self.calls += 1
            self.seconds += seconds
            if usage is not None:
                self.prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
                self.completion_tokens += getattr(usage, "completion_tokens", 0) or 0

    def to_dict(self) -> dict[str, Any]:
        return {"calls": self.calls, "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens, "failures": self.failures,
                "seconds": round(self.seconds, 1)}


_SEMAPHORE = threading.BoundedSemaphore(int(os.environ.get("LEGALLESS_MAX_CONCURRENCY", "4")))


class OpenAIJSONModel:
    """Strict-JSON chat client. Model defaults to ``LEGALLESS_MODEL`` or ``gpt-6.1-sol``."""

    def __init__(self, model: str | None = None, reasoning_effort: str | None = None,
                 retries: int = 6) -> None:
        from openai import OpenAI  # imported lazily so the core package has no hard dependency

        self.client = OpenAI(base_url=os.environ.get("OPENAI_API_BASE") or None)
        self.model = model or os.environ.get("LEGALLESS_MODEL", "gpt-6.1-sol")
        self.reasoning_effort = reasoning_effort or os.environ.get("LEGALLESS_EFFORT", "medium")
        self.retries = retries
        self.log = CallLog()

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any], name: str,
                      max_tokens: int = 4000) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.retries):
            started = time.time()
            try:
                kwargs: dict[str, Any] = dict(
                    model=self.model,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                    response_format={"type": "json_schema",
                                     "json_schema": {"name": name, "strict": True, "schema": schema}},
                    max_completion_tokens=max_tokens,
                )
                if self.reasoning_effort:
                    kwargs["reasoning_effort"] = self.reasoning_effort
                with _SEMAPHORE:
                    resp = self.client.chat.completions.create(**kwargs)
                self.log.add(resp.usage, time.time() - started)
                if not resp.choices:
                    raise ValueError(f"no choices in response: {str(resp.model_dump())[:400]}")
                content = resp.choices[0].message.content
                if not content:
                    raise ValueError(f"empty content (finish_reason={resp.choices[0].finish_reason})")
                return json.loads(content)
            except Exception as exc:  # network, schema or truncation errors -> retry
                last_error = exc
                with self.log.lock:
                    self.log.failures += 1
                import sys
                print(f'[llm] {name} attempt {attempt + 1} failed: {str(exc)[:300]}', file=sys.stderr)
                time.sleep(min(60, 8 * (attempt + 1)))
        raise RuntimeError(f"LLM call '{name}' failed after {self.retries} attempts: {last_error}")
