"""Independent constraint verification with a non-generative evaluation model.

    python -m harness.constraint_check --run-id 2026-10-22

The software-engineering-production track publishes a *violation rate*: how often
a model broke a hard constraint it was given ("no new services", "at most EUR
600 a month", "no window over 5 minutes"). That number is designed to be quoted,
which means it has to survive someone checking it.

The judge already answers each constraint's yes/no check with a quote. This
module asks the same questions of a second model of a different kind: an
evaluation model (TypeSafe AI's Jev, via the gateway's `/v1/evaluate`
endpoint) that does not write prose at all. It receives the task and the archived
response as `state`, and the checks as typed boolean questions, and returns a
probability for each. It cannot be talked into a verdict by a fluent response,
and it shares no family with any model under test or with the judge.

A violation is reported as **confirmed** only when the judge's verdict is
`violated` AND the verifier's probability that the constraint was broken is at
least 0.5 while its probability that the response explicitly acknowledged and
justified the break is below 0.5. Judge-only and verifier-only violations are
published too, as is the agreement rate, so a reader can see how much the
headline depends on either instrument.

Records go to `runs/<id>/constraints/<model>/<category>/<item>.json` with the
exact questions asked, their hash, the verifier model id, the raw answers, and
the gateway generation id and cost. Like everything else in a run folder they are
written once and never edited.
"""
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console

from .config import ModelSpec, concurrency, load_env, load_registry, run_dir
from .dataset import CONSTRAINT_CATEGORIES, Item, load_all

console = Console()

VERIFIER_PROTOCOL_VERSION = "cv-1.0.0"
THRESHOLD = 0.5

# The verifier's context limit is 32k tokens for state plus the longest
# question. Responses are capped at 16k completion tokens, so they fit; this
# character cap only exists so that a pathological response produces a recorded
# truncation flag instead of a failed request.
MAX_STATE_CHARS = 100_000

_ACK_TEMPLATE = (
    "Does the response explicitly acknowledge that its proposal breaks or relaxes "
    "this constraint - \"{text}\" - and give a justification for doing so?"
)


@dataclass(frozen=True)
class VerifierSpec:
    model_id: str
    base_url: str
    api_key_env: str
    timeout_s: int = 120
    max_retries: int = 4

    @property
    def api_key(self) -> str | None:
        import os
        return os.environ.get(self.api_key_env)


def load_verifier() -> VerifierSpec:
    registry = load_registry()
    doc = registry.raw.get("constraint_verifier") or {}
    if not doc.get("model_id"):
        raise SystemExit("data/models.yaml has no constraint_verifier.model_id")
    base = registry.judge.base_url.rstrip("/")
    return VerifierSpec(
        model_id=doc["model_id"],
        base_url=base,
        api_key_env=doc.get("api_key_env", registry.judge.api_key_env),
        timeout_s=int(doc.get("timeout_s", 120)),
        max_retries=int(doc.get("max_retries", 4)),
    )


def questions_for(item: Item) -> dict[str, dict[str, str]]:
    qs: dict[str, dict[str, str]] = {}
    for c in item.constraints:
        qs[f"{c['id']}_broken"] = {"type": "boolean", "instructions": c["check"]}
        qs[f"{c['id']}_acknowledged"] = {
            "type": "boolean", "instructions": _ACK_TEMPLATE.format(text=c["text"]),
        }
    return qs


def question_hash(qs: dict[str, Any]) -> str:
    blob = json.dumps(qs, sort_keys=True, ensure_ascii=False) + VERIFIER_PROTOCOL_VERSION
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def build_state(item: Item, response_text: str) -> tuple[str, bool]:
    response = response_text.strip()
    truncated = False
    if len(response) > MAX_STATE_CHARS:
        response, truncated = response[:MAX_STATE_CHARS], True
    state = (
        "TASK GIVEN TO AN AI MODEL:\n"
        f"{item.prompt.strip()}\n\n"
        "THE MODEL'S RESPONSE (evaluate this):\n"
        f"{response}"
    )
    return state, truncated


def verdicts_from_answers(item: Item, answers: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for c in item.constraints:
        pb = (answers.get(f"{c['id']}_broken") or {}).get("probability")
        pa = (answers.get(f"{c['id']}_acknowledged") or {}).get("probability")
        if pb is None or pa is None:
            verdict = "missing"
        elif pb >= THRESHOLD and pa < THRESHOLD:
            verdict = "violated"
        elif pb >= THRESHOLD:
            verdict = "relaxed_explicitly"
        else:
            verdict = "kept"
        out[c["id"]] = {"verdict": verdict, "p_broken": pb, "p_acknowledged": pa}
    return out


def evaluate(spec: VerifierSpec, item: Item, response_text: str) -> dict[str, Any]:
    qs = questions_for(item)
    state, truncated = build_state(item, response_text)
    body = {"model": spec.model_id, "state": state, "questions": qs}
    started = time.time()
    last_err = None
    for attempt in range(1, spec.max_retries + 1):
        try:
            resp = httpx.post(
                f"{spec.base_url}/evaluate",
                json=body,
                headers={"Authorization": f"Bearer {spec.api_key}"},
                timeout=spec.timeout_s,
            )
            if resp.status_code >= 500 or resp.status_code == 429:
                raise httpx.HTTPStatusError(
                    f"{resp.status_code}: {resp.text[:200]}", request=resp.request, response=resp)
            if resp.status_code >= 400:
                last_err = f"{resp.status_code}: {resp.text[:300]}"
                break
            doc = resp.json()
            gw = (doc.get("providerMetadata") or {}).get("gateway") or {}
            answers = doc.get("answers") or {}
            return {
                "ok": True,
                "verifier_model": doc.get("model") or spec.model_id,
                "requested_model": spec.model_id,
                "protocol_version": VERIFIER_PROTOCOL_VERSION,
                "question_hash": question_hash(qs),
                "questions": qs,
                "answers": answers,
                "verdicts": verdicts_from_answers(item, answers),
                "state_truncated": truncated,
                "usage": doc.get("usage"),
                "cost_usd": float(gw["cost"]) if gw.get("cost") is not None else None,
                "generation_id": gw.get("generationId"),
                "latency_s": round(time.time() - started, 3),
                "attempts": attempt,
            }
        except (httpx.HTTPError, ValueError) as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            time.sleep(min(2 ** attempt, 20))
    return {
        "ok": False, "error": last_err, "requested_model": spec.model_id,
        "protocol_version": VERIFIER_PROTOCOL_VERSION, "question_hash": question_hash(qs),
        "questions": qs, "latency_s": round(time.time() - started, 3),
    }


def check_path(root: Path, model_key: str, category: str, item_id: str) -> Path:
    return root / "constraints" / model_key / category / f"{item_id}.json"


def phase_constraints(
    root: Path,
    models: list[ModelSpec],
    items_by_category: dict[str, list[Item]],
    workers: int,
) -> int:
    """Verify every constraint item for every model. Returns records written."""
    from .run_eval import raw_path, read_json, usable_raw, write_json

    spec = load_verifier()
    if not spec.api_key:
        raise SystemExit(f"Missing API key env var {spec.api_key_env} for the verifier")

    jobs: list[tuple[str, Item, str]] = []
    cached = 0
    for m in models:
        for category, items in items_by_category.items():
            if category not in CONSTRAINT_CATEGORIES:
                continue
            for item in items:
                dest = check_path(root, m.key, category, item.id)
                prev = read_json(dest)
                if prev and prev.get("ok") and prev.get("question_hash") == question_hash(questions_for(item)):
                    cached += 1
                    continue
                raw = read_json(raw_path(root, m.key, category, item.id))
                if not usable_raw(raw):
                    continue
                jobs.append((m.key, item, raw["text"]))

    if cached:
        console.print(f"[dim]Reusing {cached} constraint verification(s).[/dim]")
    if not jobs:
        return 0
    console.print(f"Verifying constraints with [bold]{spec.model_id}[/bold]: {len(jobs)} response(s)")

    def work(model_key: str, item: Item, text: str) -> dict[str, Any]:
        rec = evaluate(spec, item, text)
        rec.update({"model_key": model_key, "item_id": item.id, "category": item.category,
                    "item_content_hash": item.content_hash})
        write_json(check_path(root, model_key, item.category, item.id), rec)
        return rec

    failures = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(work, mk, it, tx) for mk, it, tx in jobs]
        for fut in as_completed(futures):
            rec = fut.result()
            if not rec.get("ok"):
                failures += 1
                console.print(f"[yellow]verifier issue[/yellow] {rec['model_key']}/{rec['item_id']}: {rec.get('error')}")
    if failures:
        console.print(f"[yellow]{failures} verification(s) failed; re-run to retry them.[/yellow]")
    return len(jobs) - failures


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="constraint_check", description=__doc__.split("\n\n")[0])
    p.add_argument("--run-id", required=True)
    p.add_argument("--models", default="")
    p.add_argument("--concurrency", type=int, default=0)
    args = p.parse_args(argv)
    load_env()
    registry = load_registry()
    models = registry.enabled_models()
    if args.models:
        models = [registry.by_key(k.strip()) for k in args.models.split(",") if k.strip()]
    items = load_all(sorted(CONSTRAINT_CATEGORIES))
    n = phase_constraints(run_dir(args.run_id), models, items, args.concurrency or concurrency())
    console.print(f"[green]{n} constraint verification(s) written.[/green]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
