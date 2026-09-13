"""Judge model wrapper.

EVERY score this module produces carries, in the record itself:

  * the judge model id actually used
  * the judge prompt version and a hash of the exact prompt text
  * a hash of the exact rubric text handed to the judge
  * the scoring engine used
  * the methodology version

Judge-scored benchmarks are only
comparable across time if the judge is held fixed, and the usual way that goes
wrong is silent: someone improves a rubric, scores shift by four points, and a
year later nobody can tell whether a model got better or the wording did. Hashes
in the record make that undetectable change detectable, because they move even
when a changelog entry is forgotten.

Changing the judge model or any rubric wording is a METHODOLOGY VERSION change.
See docs/METHODOLOGY.md.

TWO ENGINES
-----------
`native` (default): one judge call per (item, model) returns scores and written
reasoning for every dimension as JSON. This is a G-Eval in the original sense - 
rubric, explicit evaluation steps, chain-of-thought, anchored scale - evaluated
in a single pass.

`deepeval`: DeepEval's own `GEval` implementation, one call per dimension, using
the same rubric text through a gateway-backed `DeepEvalBaseLLM`.

The engines exist to check each other. `native` is the default because it costs
roughly one third as much per item and a monthly public benchmark has to be
affordable to re-run; `deepeval` is run on a sample each cycle to confirm the two
agree. If they diverge materially, that is a finding about our scoring and is
reported, not smoothed over. Cross-engine agreement is recorded in the run
summary.
"""
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from . import METHODOLOGY_VERSION
from .config import JudgeSpec
from .dataset import Item
from .metrics import SCALE_DESCRIPTION, get_metric, rubric_hash
from .models import judge_generate

# ---------------------------------------------------------------------------
# Judge prompt. Versioned. Any edit below is a methodology change.
# ---------------------------------------------------------------------------

JUDGE_PROMPT_VERSION = "jp-1.0.0"

JUDGE_SYSTEM_PROMPT = """You are an impartial evaluation judge for an open, public AI benchmark.

You will be shown a rubric, a prompt that was given to an AI model, and that model's response. Your job is to score the response against each rubric dimension.

Rules you must follow:

1. Score ONLY against the rubric given. Do not import criteria of your own.
2. You do not know which model produced the response. Do not speculate about it. Do not let writing style, formatting, or apparent house voice influence the score.
3. Reason before you score. For each dimension, work through the evaluation steps and cite specific evidence from the response - quote it - before giving a number.
4. Length is not quality. Confidence is not quality. Professional formatting is not quality. A long, fluent, well-formatted response that does not do what the rubric asks must receive a low score.
5. Use the full range of the scale. If a response deserves 0 or 4, give it. Clustering everything at 2 makes the benchmark useless.
6. If the response is empty, truncated mid-sentence, or is an error message rather than an answer, score 0 on every dimension and say so explicitly in your reasoning.
7. Do not reward or penalise a response for the political, moral, or institutional position it takes. Score the quality of the work, never your agreement with it.

Output ONLY a single JSON object, with no surrounding prose and no markdown code fence:

{
  "dimensions": {
    "<dimension_key>": {
      "reasoning": "<specific evidence from the response, quoting it, then your justification>",
      "score": <integer 0-4>
    }
  },
  "overall_note": "<one sentence on the single most important thing about this response>",
  "flags": ["<optional: refusal | truncated | fabrication_suspected | off_task | empty>"]
}

Include every dimension key from the rubric, exactly as spelled. Scores must be integers from 0 to 4."""

JUDGE_USER_TEMPLATE = """{rubric}

---

# The prompt that was given to the model

{prompt}

{item_context}

---

# The model's response

<response>
{response}
</response>

---

Score the response against every dimension in the rubric above. Output only the JSON object."""


def _judge_prompt_hash() -> str:
    payload = JUDGE_SYSTEM_PROMPT + "\n===\n" + JUDGE_USER_TEMPLATE + "\n===\n" + SCALE_DESCRIPTION
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


JUDGE_PROMPT_HASH = _judge_prompt_hash()


# ---------------------------------------------------------------------------
# Score record
# ---------------------------------------------------------------------------


@dataclass
class ScoreRecord:
    """One judged (item, model) pair, with full provenance."""

    item_id: str
    category: str
    model_key: str

    score: float                       # 0-100 weighted category score
    dimension_scores: dict[str, int] = field(default_factory=dict)   # raw 0-4
    dimension_reasoning: dict[str, str] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)
    overall_note: str = ""

    ok: bool = True
    error: str | None = None

    # Provenance - written on every record, every run, without exception.
    judge_model: str = ""
    judge_prompt_version: str = JUDGE_PROMPT_VERSION
    judge_prompt_hash: str = JUDGE_PROMPT_HASH
    rubric_version: str = ""
    rubric_hash: str = ""
    metric_engine: str = "native"
    methodology_version: str = METHODOLOGY_VERSION

    judge_latency_s: float = 0.0
    judge_cost_usd: float | None = None
    judge_raw_output: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _extract_json(text: str) -> dict[str, Any] | None:
    """Pull a JSON object out of judge output.

    Judges are instructed not to use a code fence and mostly comply, but a
    scoring pipeline that dies on a stray fence is a pipeline that loses runs.
    Falls back to brace matching.
    """
    if not text:
        return None

    candidates: list[str] = []
    fenced = _FENCE_RE.search(text)
    if fenced:
        candidates.append(fenced.group(1))
    candidates.append(text.strip())

    start = text.find("{")
    if start != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[start : i + 1])
                    break

    for cand in candidates:
        try:
            parsed = json.loads(cand)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            continue
    return None


def _coerce_score(value: Any) -> int:
    """Clamp a judge score to the 0-4 integer scale."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(4, int(round(num))))


def _item_context(item: Item) -> str:
    """Per-item context appended to the judge prompt.

    Deliberately never includes the item's `rationale`. That field explains why
    the item is in the benchmark and often names the failure mode we expect - 
    handing it to the judge would tell it what to find, and it would find it.
    """
    parts: list[str] = []
    if item.reference:
        parts.append(f"# Reference answer\n\n{item.reference.strip()}")
    if item.rubric_notes:
        parts.append(f"# Item-specific rubric notes\n\n{item.rubric_notes.strip()}")
    if item.category == "ethics-philosophy" and item.contested:
        parts.append(
            "# Note on this item\n\nThis question is genuinely contested among "
            "serious thinkers. There is no consensus answer. Do not award or deduct "
            "points for which position the response takes."
        )
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Native engine
# ---------------------------------------------------------------------------


def score_native(
    spec: JudgeSpec, item: Item, model_key: str, response_text: str
) -> ScoreRecord:
    """Score one response with a single structured judge call."""
    metric = get_metric(item.category)
    rec = ScoreRecord(
        item_id=item.id,
        category=item.category,
        model_key=model_key,
        score=0.0,
        judge_model=spec.model_id,
        rubric_version=metric.version,
        rubric_hash=rubric_hash(item.category),
        metric_engine="native",
    )

    # An empty response is scored 0 without spending a judge call on it. The
    # reason is recorded so that a zero from a failed generation is always
    # distinguishable from a zero the judge actually awarded.
    if not (response_text or "").strip():
        rec.dimension_scores = {d.key: 0 for d in metric.dimensions}
        rec.dimension_reasoning = {
            d.key: "Empty or failed model response; not sent to judge." for d in metric.dimensions
        }
        rec.flags = ["empty"]
        rec.overall_note = "Model produced no usable response."
        rec.score = 0.0
        return rec

    user_prompt = JUDGE_USER_TEMPLATE.format(
        rubric=metric.rubric_block(),
        prompt=item.prompt.strip(),
        item_context=_item_context(item),
        response=response_text.strip(),
    )

    completion = judge_generate(spec, JUDGE_SYSTEM_PROMPT, user_prompt)
    rec.judge_latency_s = completion.latency_s
    rec.judge_cost_usd = completion.cost_usd
    rec.judge_raw_output = completion.text

    if not completion.ok:
        rec.ok = False
        rec.error = f"judge_call_failed: {completion.error}"
        return rec

    parsed = _extract_json(completion.text)

    if parsed is None:
        # One retry with a blunter instruction before giving up.
        #
        # Cheaper judges follow the output contract less reliably than frontier
        # ones. The first DeepSeek run failed to parse on roughly 8% of items,
        # which would have silently dropped ~70 items from the benchmark.
        # Dropping an item because the judge prefaced its JSON with a sentence is
        # a defect in our pipeline, not a fact about the model being evaluated,
        # and it would land unevenly across categories.
        #
        # The retry re-asks the SAME question with the same rubric. It does not
        # coach the judge toward any score, so it cannot bias the result. Both
        # attempts are kept in judge_raw_output so a reviewer can see it happened.
        retry = judge_generate(
            spec,
            JUDGE_SYSTEM_PROMPT,
            user_prompt
            + "\n\n---\n\nIMPORTANT: respond with the raw JSON object ONLY. "
              "No preamble, no explanation outside the JSON, no markdown code "
              "fence. Your reply must begin with { and end with }.",
        )
        rec.judge_latency_s = round(rec.judge_latency_s + retry.latency_s, 3)
        if retry.cost_usd is not None:
            rec.judge_cost_usd = round((rec.judge_cost_usd or 0.0) + retry.cost_usd, 6)
        rec.judge_raw_output = (
            completion.text + "\n\n=== UNPARSEABLE; RETRIED ===\n\n" + retry.text
        )
        if retry.ok:
            parsed = _extract_json(retry.text)
        rec.flags = ["judge_retry"]

    if parsed is None:
        rec.ok = False
        rec.error = "judge_output_unparseable_after_retry"
        return rec

    dims = parsed.get("dimensions") or {}
    scores: dict[str, int] = {}
    reasoning: dict[str, str] = {}
    missing: list[str] = []
    for dim in metric.dimensions:
        entry = dims.get(dim.key)
        if not isinstance(entry, dict):
            missing.append(dim.key)
            scores[dim.key] = 0
            reasoning[dim.key] = "Judge omitted this dimension."
            continue
        scores[dim.key] = _coerce_score(entry.get("score"))
        reasoning[dim.key] = str(entry.get("reasoning", "")).strip()

    rec.dimension_scores = scores
    rec.dimension_reasoning = reasoning
    rec.overall_note = str(parsed.get("overall_note", "")).strip()
    flags = parsed.get("flags")
    # Extend rather than assign: a `judge_retry` flag set above must survive,
    # otherwise a retried score looks identical to a clean one in the record.
    if isinstance(flags, list):
        rec.flags = rec.flags + [str(f) for f in flags]
    rec.score = metric.weighted_score(scores)

    if missing:
        # Partial output still yields a score, but it is marked so aggregation
        # can exclude it and a reviewer can see how often the judge misbehaved.
        rec.ok = False
        rec.error = f"judge_missing_dimensions: {','.join(missing)}"

    return rec


# ---------------------------------------------------------------------------
# DeepEval engine (cross-validation)
# ---------------------------------------------------------------------------


def _deepeval_llm(spec: JudgeSpec):
    """Wrap the gateway judge as a DeepEvalBaseLLM.

    Imported lazily so that the default path never pays DeepEval's import cost
    and the harness still runs if DeepEval is not installed.
    """
    from deepeval.models import DeepEvalBaseLLM

    class GatewayJudge(DeepEvalBaseLLM):
        def __init__(self, judge_spec: JudgeSpec) -> None:
            self.spec = judge_spec
            super().__init__(model_name=judge_spec.model_id)

        def load_model(self):
            return self.spec.model_id

        def generate(self, prompt: str, *args, **kwargs) -> str:
            completion = judge_generate(self.spec, JUDGE_SYSTEM_PROMPT, prompt)
            if not completion.ok:
                raise RuntimeError(f"Judge call failed: {completion.error}")
            return completion.text

        async def a_generate(self, prompt: str, *args, **kwargs) -> str:
            return self.generate(prompt, *args, **kwargs)

        def get_model_name(self) -> str:
            return self.spec.model_id

    return GatewayJudge(spec)


def score_deepeval(
    spec: JudgeSpec, item: Item, model_key: str, response_text: str
) -> ScoreRecord:
    """Score one response using DeepEval's GEval, one call per dimension.

    Uses the same rubric text as the native engine so the two are comparable.
    DeepEval reports 0-1; it is rescaled onto the shared 0-4 anchored scale.
    """
    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCase, LLMTestCaseParams

    metric = get_metric(item.category)
    rec = ScoreRecord(
        item_id=item.id,
        category=item.category,
        model_key=model_key,
        score=0.0,
        judge_model=spec.model_id,
        rubric_version=metric.version,
        rubric_hash=rubric_hash(item.category),
        metric_engine="deepeval",
    )

    if not (response_text or "").strip():
        rec.dimension_scores = {d.key: 0 for d in metric.dimensions}
        rec.dimension_reasoning = {d.key: "Empty response." for d in metric.dimensions}
        rec.flags = ["empty"]
        rec.score = 0.0
        return rec

    judge_llm = _deepeval_llm(spec)
    test_case = LLMTestCase(input=item.prompt.strip(), actual_output=response_text.strip())

    scores: dict[str, int] = {}
    reasoning: dict[str, str] = {}
    raw_parts: list[str] = []
    total_cost = 0.0
    errors: list[str] = []

    for dim in metric.dimensions:
        try:
            geval = GEval(
                name=dim.name,
                evaluation_steps=[
                    f"Rubric for this dimension: {dim.rubric}",
                    *dim.evaluation_steps,
                    f"Scale reference: {SCALE_DESCRIPTION}",
                ],
                evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
                model=judge_llm,
                verbose_mode=False,
            )
            geval.measure(test_case)
            # GEval reports 0-1; rescale onto the project's shared 0-4 anchors.
            scores[dim.key] = _coerce_score(round(float(geval.score) * 4))
            reasoning[dim.key] = str(geval.reason or "")
            raw_parts.append(f"[{dim.key}] score={geval.score} reason={geval.reason}")
        except Exception as exc:  # noqa: BLE001
            scores[dim.key] = 0
            reasoning[dim.key] = f"DeepEval GEval failed: {exc}"
            errors.append(f"{dim.key}:{type(exc).__name__}")

    rec.dimension_scores = scores
    rec.dimension_reasoning = reasoning
    rec.judge_raw_output = "\n".join(raw_parts)
    rec.judge_cost_usd = total_cost or None
    rec.score = metric.weighted_score(scores)
    if errors:
        rec.ok = False
        rec.error = f"deepeval_dimension_errors: {','.join(errors)}"
    return rec


ENGINES = {"native": score_native, "deepeval": score_deepeval}


def score(
    spec: JudgeSpec,
    item: Item,
    model_key: str,
    response_text: str,
    engine: str = "native",
) -> ScoreRecord:
    try:
        fn = ENGINES[engine]
    except KeyError as exc:
        raise ValueError(f"Unknown judge engine {engine!r}. Known: {list(ENGINES)}") from exc
    return fn(spec, item, model_key, response_text)


def judge_provenance(spec: JudgeSpec, engine: str) -> dict[str, Any]:
    """The provenance block written into every run summary."""
    from .metrics import all_rubric_hashes

    return {
        "judge_model": spec.model_id,
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
        "judge_prompt_hash": JUDGE_PROMPT_HASH,
        "judge_temperature": spec.temperature,
        "judge_max_tokens": spec.max_tokens,
        "metric_engine": engine,
        "methodology_version": METHODOLOGY_VERSION,
        "rubric_hashes": all_rubric_hashes(),
    }
