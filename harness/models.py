"""Model-agnostic completion wrappers.

Design goal: adding a model to the benchmark costs exactly one entry in
`data/models.yaml` and zero lines of code.

All providers are reached through the Vercel AI Gateway, which exposes a single
OpenAI-compatible endpoint for Anthropic, OpenAI, Google, Mistral, DeepSeek,
Moonshot, Meta and others. That is why there is one transport here rather than
one client per lab.

The `Transport` protocol below is the extension point: if a model ever needs to
be reached directly (a private endpoint, a self-hosted open-weights model, a
provider the gateway does not carry), implement `Transport`, register it in
`TRANSPORTS`, and set `transport: <name>` on that model registry entry. No call
site changes.
"""
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import json
import random
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from openai import OpenAI

from .config import JudgeSpec, ModelSpec

# Errors worth retrying: transient network, rate limit, provider 5xx.
_RETRYABLE_MARKERS = (
    "rate limit", "rate_limit", "429", "500", "502", "503", "504",
    "timeout", "timed out", "connection", "overloaded", "temporarily",
    "capacity", "unavailable",
)


@dataclass
class Completion:
    """One model response plus everything needed to audit how it was produced."""

    model_key: str
    model_id: str
    provider: str
    text: str
    ok: bool
    error: str | None = None
    latency_s: float = 0.0
    attempts: int = 1
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float | None = None
    finish_reason: str | None = None
    request_fingerprint: str = ""
    request_params: dict[str, Any] = field(default_factory=dict)
    timestamp_utc: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def fingerprint(payload: dict[str, Any]) -> str:
    """Stable hash of the exact request. Lets a reviewer prove two runs asked
    the same question in the same way."""
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(m in msg for m in _RETRYABLE_MARKERS)


class Transport(Protocol):
    """Anything that can turn a prompt into text for a given model spec."""

    def complete(
        self,
        *,
        model_id: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        timeout_s: int,
        api_key: str,
        base_url: str,
    ) -> dict[str, Any]:
        ...


class GatewayTransport:
    """OpenAI-compatible transport. Points at the Vercel AI Gateway by default.

    Clients are cached per (base_url, api_key) so a long run reuses connections
    instead of opening one per request.
    """

    _clients: dict[tuple[str, str], OpenAI] = {}

    def _client(self, base_url: str, api_key: str, timeout_s: int) -> OpenAI:
        cache_key = (base_url, api_key)
        if cache_key not in self._clients:
            self._clients[cache_key] = OpenAI(
                base_url=base_url,
                api_key=api_key,
                timeout=timeout_s,
                max_retries=0,  # retries handled here so that they get logged
            )
        return self._clients[cache_key]

    def complete(
        self,
        *,
        model_id: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        timeout_s: int,
        api_key: str,
        base_url: str,
    ) -> dict[str, Any]:
        client = self._client(base_url, api_key, timeout_s)
        kwargs: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "max_completion_tokens": max_tokens,
        }
        # Some reasoning models reject any temperature but their default.
        if temperature is not None:
            kwargs["temperature"] = temperature

        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            detail = str(exc).lower()
            if "temperature" in detail and "temperature" in kwargs:
                kwargs.pop("temperature")
                resp = client.chat.completions.create(**kwargs)
            elif "max_completion_tokens" in detail:
                kwargs.pop("max_completion_tokens", None)
                kwargs["max_tokens"] = max_tokens
                resp = client.chat.completions.create(**kwargs)
            else:
                raise

        choice = resp.choices[0] if resp.choices else None
        usage = resp.usage
        # The gateway reports real dollar cost per call. Recording it makes the
        # cost of a run auditable rather than estimated.
        cost = None
        if usage is not None:
            cost = getattr(usage, "cost", None)
            if cost is None:
                cost = (getattr(usage, "model_extra", None) or {}).get("cost")

        return {
            "text": (choice.message.content if choice and choice.message else "") or "",
            "finish_reason": getattr(choice, "finish_reason", None) if choice else None,
            "prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
            "completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
            "cost_usd": float(cost) if cost is not None else None,
        }


TRANSPORTS: dict[str, Transport] = {"gateway": GatewayTransport()}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _call_with_retries(
    transport: Transport,
    *,
    model_key: str,
    model_id: str,
    provider: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    timeout_s: int,
    max_retries: int,
    api_key: str,
    base_url: str,
) -> Completion:
    params = {
        "model": model_id,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    fp = fingerprint(params)
    started = time.time()
    last_err: str | None = None

    for attempt in range(1, max_retries + 1):
        try:
            out = transport.complete(
                model_id=model_id,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout_s=timeout_s,
                api_key=api_key,
                base_url=base_url,
            )
            return Completion(
                model_key=model_key,
                model_id=model_id,
                provider=provider,
                text=out["text"],
                ok=True,
                latency_s=round(time.time() - started, 3),
                attempts=attempt,
                prompt_tokens=out.get("prompt_tokens"),
                completion_tokens=out.get("completion_tokens"),
                cost_usd=out.get("cost_usd"),
                finish_reason=out.get("finish_reason"),
                request_fingerprint=fp,
                request_params={k: v for k, v in params.items() if k != "messages"},
                timestamp_utc=_now(),
            )
        except Exception as exc:  # noqa: BLE001
            last_err = f"{type(exc).__name__}: {exc}"
            if attempt >= max_retries or not _is_retryable(exc):
                break
            # Exponential backoff with jitter, capped, so one flaky provider
            # cannot stall a whole run.
            time.sleep(min(2 ** attempt + random.random(), 30))

    return Completion(
        model_key=model_key,
        model_id=model_id,
        provider=provider,
        text="",
        ok=False,
        error=last_err,
        latency_s=round(time.time() - started, 3),
        attempts=max_retries,
        request_fingerprint=fp,
        request_params={k: v for k, v in params.items() if k != "messages"},
        timestamp_utc=_now(),
    )


# Deliberately minimal. A system prompt that coaches the model toward a house
# style would contaminate exactly what this benchmark measures: how models
# behave by default on under-covered prompts.
DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant."


def generate(spec: ModelSpec, prompt: str, system: str | None = None) -> Completion:
    """Run one prompt against one registered model."""
    api_key = spec.api_key
    if not api_key:
        return Completion(
            model_key=spec.key,
            model_id=spec.model_id,
            provider=spec.provider,
            text="",
            ok=False,
            error=f"Missing API key: set {spec.api_key_env} (see .env.example)",
            timestamp_utc=_now(),
        )

    messages = [
        {"role": "system", "content": system or DEFAULT_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    return _call_with_retries(
        TRANSPORTS["gateway"],
        model_key=spec.key,
        model_id=spec.model_id,
        provider=spec.provider,
        messages=messages,
        temperature=spec.temperature,
        max_tokens=spec.max_tokens,
        timeout_s=spec.timeout_s,
        max_retries=spec.max_retries,
        api_key=api_key,
        base_url=spec.base_url,
    )


def judge_generate(spec: JudgeSpec, system: str, prompt: str) -> Completion:
    """Run one judging call. Same transport, same logging, same audit trail."""
    api_key = spec.api_key
    if not api_key:
        return Completion(
            model_key="judge",
            model_id=spec.model_id,
            provider="judge",
            text="",
            ok=False,
            error=f"Missing API key: set {spec.api_key_env} (see .env.example)",
            timestamp_utc=_now(),
        )
    return _call_with_retries(
        TRANSPORTS["gateway"],
        model_key="judge",
        model_id=spec.model_id,
        provider="judge",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=spec.temperature,
        max_tokens=spec.max_tokens,
        timeout_s=spec.timeout_s,
        max_retries=spec.max_retries,
        api_key=api_key,
        base_url=spec.base_url,
    )
