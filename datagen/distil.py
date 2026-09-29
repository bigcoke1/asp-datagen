"""The distilabel version of the pipeline: its custom LLM client and steps.

This is the prototype's approach (the generation page §4, "Distilabel is the backbone") carried
onto the current method: code samples the facts, a teacher writes the surface, the bundle is
assembled and validated, two teachers label it blind, and a gateway routes each label three
ways. The DAG is in `datagen.distil_run`. These classes live in a module rather than beside the
DAG because distilabel runs each step in its own spawned process, which has to import them.

Complex values travel between steps as JSON strings. distilabel buffers rows in Arrow, where a
nested column whose shape changes between batches can fail the cast (distilabel issue #935).
"""
import asyncio
import hashlib
import json
import random
import statistics
import time
from collections import Counter
from typing import Any, Dict, List, Optional

from distilabel.models.llms.base import AsyncLLM
from distilabel.steps import Step, StepInput
from distilabel.steps.tasks import Task
from distilabel.typing import StepOutput
from pydantic import PrivateAttr

from datagen import assemble, generate, label, scenarios, validate
from datagen.contract import coverage
from datagen.llm import GEN_MIX, OLLAMA_HOST, log_call, think_setting


def plan(seed: int, idx: int) -> tuple[random.Random, dict, str]:
    """The draws `run.py` makes for bundle `idx`, in the same order, so both pipelines agree on the
    scenario and generator for a seed and `assemble` continues from the same generator state."""
    rng = random.Random(seed * 1000 + idx)
    s = scenarios.sample(rng)
    teacher = rng.choices(list(GEN_MIX), weights=list(GEN_MIX.values()))[0]
    return rng, s, teacher


class OllamaChat(AsyncLLM):
    """Ollama's native chat API, called the way the pilot calls it.

    distilabel 1.5.3's own `OllamaLLM` cannot: it accepts `format="json"` but not a JSON schema,
    has no way to turn thinking off, and a failed call raises inside its error handler. This
    client adds three things the pipeline needs:
    - a JSON schema per row, passed in by the task as `(messages, schema)`;
    - per-call timing written to `call_log`, since distilabel records token counts only;
    - scheduling for one local GPU. A row holds its turn for all k samples, and rows take turns
      in the order they arrive, which `ExpandCategories` groups by bundle. So every call on one
      bundle runs back to back and reuses the prefix Ollama cached for it. A turn per call
      instead would interleave bundles and make every call a cold read (data/pilot2/
      aborted-interleaved). Up to `max_concurrency` rows run side by side; keep it at 1 on a
      Mac (`distil_run --parallel` has the measurement).

    A failed call returns None for that generation only. It does not null the whole batch.
    """

    model: str
    stage: str = ""
    temperature: float = 0.7
    num_ctx: int = 8192
    max_concurrency: int = 1
    call_log: Optional[str] = None
    timeout: float = 1800

    _client: Any = PrivateAttr(default=None)
    _sem: Any = PrivateAttr(default=None)

    def load(self) -> None:
        super().load()
        import httpx

        self._client = httpx.AsyncClient(base_url=OLLAMA_HOST, timeout=self.timeout)

    @property
    def model_name(self) -> str:
        return self.model

    async def _call(self, messages: list, schema: Optional[dict], seed: int) -> tuple[Optional[str], dict]:
        body = {"model": self.model, "messages": messages, "stream": False,
                "options": {"temperature": self.temperature, "num_ctx": self.num_ctx, "seed": seed}}
        if schema is not None:
            body["format"] = schema
        think = think_setting(self.model)
        if think is not None:
            body["think"] = think
        t0 = time.time()
        try:
            r = await self._client.post("/api/chat", json=body)
            r.raise_for_status()
            resp, error = r.json(), None
        except Exception as e:  # noqa: BLE001 -- recorded in the call log and as a None generation
            resp, error = {}, f"{type(e).__name__}: {e}"
        t1 = time.time()
        log_call(self.call_log, self.stage, self.model, t0, t1, resp, error)
        text = (resp.get("message") or {}).get("content") if not error else None
        return text, resp

    async def agenerate(self, input: Any, num_generations: int = 1) -> Dict[str, Any]:
        # No **kwargs: distilabel reads this signature for runtime parameters and would demand one called "kwargs".
        if self._sem is None:  # asyncio primitives bind to the running loop, so make it here
            self._sem = asyncio.Semaphore(self.max_concurrency)  # wakes waiters first-come, first-served
        messages, schema = input if isinstance(input, tuple) else (input, None)
        seed = int(hashlib.sha256(json.dumps(messages, ensure_ascii=False).encode()).hexdigest()[:7], 16)
        gens, ins, outs = [], [], []
        async with self._sem:
            for i in range(num_generations):
                out, resp = await self._call(messages, schema, seed + i)
                gens.append(out)
                ins.append(resp.get("prompt_eval_count", 0))
                outs.append(resp.get("eval_count", 0))
        return {"generations": gens, "statistics": {"input_tokens": ins, "output_tokens": outs}}


class WriteSurface(Task):
    """The teacher writes the names and text a real bundle would carry, and nothing else.

    The prompt is `generate.prompt`, which `generate.guard` has already checked for risk words.
    """

    @property
    def inputs(self) -> List[str]:
        return ["surface_prompt", "surface_schema"]

    @property
    def outputs(self) -> List[str]:
        return ["surface_json", "model_name"]

    def format_input(self, input: Dict[str, Any]) -> Any:
        messages = [{"role": "system", "content": generate.SYSTEM}, {"role": "user", "content": input["surface_prompt"]}]
        return messages, json.loads(input["surface_schema"])

    def format_output(self, output: Optional[str], input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            json.loads(output or "")
        except json.JSONDecodeError:
            return {"surface_json": None}
        return {"surface_json": output}


class AssembleBundle(Step):
    """Scenario + surface -> bundle, validated against the Evidence Bundle Schema (as `run.py` does)."""

    seed: int

    @property
    def inputs(self) -> List[str]:
        return ["idx", "surface_json"]

    @property
    def outputs(self) -> List[str]:
        return ["bundle_id", "bundle_json", "schema_problems"]

    def process(self, *batches: StepInput) -> StepOutput:  # type: ignore[override]
        # One batch per generator step: a step with several predecessors must take `*args`.
        inputs = [row for batch in batches for row in batch]
        for row in inputs:
            rng, s, _ = plan(self.seed, row["idx"])
            if row["surface_json"] is None:
                row.update(bundle_id=f"failed-{row['idx']:04d}", bundle_json=None,
                           schema_problems=json.dumps(["the teacher returned no usable surface"]))
                continue
            b = assemble.bundle(s, json.loads(row["surface_json"]), row["idx"], rng)
            row.update(bundle_id=b["bundle_id"], bundle_json=json.dumps(b, ensure_ascii=False),
                       schema_problems=json.dumps(validate.problems(b)))
        yield inputs


class ExpandCategories(Step):
    """One row per bundle x category, carrying the required inputs that are blind (coverage profiler)."""

    categories: List[str]

    @property
    def inputs(self) -> List[str]:
        return ["bundle_json", "schema_problems"]

    @property
    def outputs(self) -> List[str]:
        return ["category", "missing"]

    def process(self, inputs: StepInput) -> StepOutput:  # type: ignore[override]
        yield [{**row, "category": cat, "missing": ",".join(coverage(json.loads(row["bundle_json"]), cat))}
               for row in inputs for cat in self.categories]


class KeepWhere(Step):
    """Pass on only the rows whose `column` is (or, with `negate`, is not) `value`."""

    column: str
    value: Any
    negate: bool = False

    @property
    def inputs(self) -> List[str]:
        return [self.column]

    def process(self, inputs: StepInput) -> StepOutput:  # type: ignore[override]
        yield [row for row in inputs if (row[self.column] == self.value) != self.negate]


class LabelBundle(Task):
    """Blind labelling: the teacher sees the bundle and the category, and nothing else in the row.

    Rows carry the scenario forward (distilabel keeps every upstream column), so blindness rests
    on `format_input` reading only these two columns. Output is one `score` and `reason` per
    sample. With `group_generations=True` the k samples arrive as lists.
    """

    @property
    def inputs(self) -> List[str]:
        return ["bundle_json", "category"]

    @property
    def outputs(self) -> List[str]:
        return ["score", "reason", "model_name"]

    def format_input(self, input: Dict[str, Any]) -> Any:
        b = json.loads(input["bundle_json"])
        messages = [{"role": "system", "content": label.SYSTEM}, {"role": "user", "content": label.ask(b, input["category"])}]
        return messages, label.OUT

    def format_output(self, output: Optional[str], input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            out = json.loads(output or "")
        except json.JSONDecodeError:
            return {"score": None, "reason": None}
        score = out.get("score")
        ok = isinstance(score, int) and not isinstance(score, bool) and 0 <= score <= 10 and isinstance(out.get("reason"), str)
        return {"score": score if ok else None, "reason": out.get("reason") if ok else None}


def summarise(scores: List[Optional[int]], reasons: List[Optional[str]]) -> dict:
    """k samples -> the record `label.label` writes, so `check.py` and `summarize` read both pipelines alike."""
    samples = [{"score": s, "reason": r, "valid": s is not None} for s, r in zip(scores, reasons)]
    valid = [s for s in scores if s is not None]
    if not valid:
        return {"outcome": "FAILED", "samples": samples}
    counts = Counter(valid)
    return {"outcome": "SCORED", "samples": samples,
            "distribution": {str(v): round(counts.get(v, 0) / len(valid), 3) for v in range(11)},
            "median": sorted(valid)[len(valid) // 2]}


def anchor_breaches(bundle: dict, category: str, median: int) -> List[str]:
    """Labels that contradict a fact the bundle shows and the rubric anchors. Visible facts only:
    the gate reads what the labeller read, never the scenario."""
    a = bundle["attributes"]
    shown = lambda n: a[n]["status"] in ("ANSWERED", "PARTIAL")  # noqa: E731
    out = []
    if category == "containment" and shown("permissions") and shown("user") \
            and (a["permissions"]["value"] or {}).get("privileged") and a["user"]["value"] == "root" and median > 2:
        out.append(f"privileged + root scored {median}; the rubric's anchor for host control as root is 1")
    return out


class RouteLabel(Step):
    """The gateway (prototype §4.1 step 6), repurposed from graded assessments to labels.

    - auto_reject: a teacher returned no usable sample. There is nothing to train on.
    - manual_review: the teachers' medians differ by more than `max_gap`, a teacher's own samples
      spread wider than `max_spread`, or a label contradicts a rubric anchor. These go to a human
      rather than being dropped. Dropping anchor breaches would take the most dangerous bundles
      out of the corpus, which is the class-balance failure the generation page warns about.
    - auto_accept: everything else. The training target is both teachers' samples pooled.
    """

    teachers: List[str]
    max_gap: int = 1
    max_spread: int = 2

    @property
    def inputs(self) -> List[str]:
        return ["bundle_json", "category"] + [f"scores_{i}" for i in range(len(self.teachers))]

    @property
    def outputs(self) -> List[str]:
        return ["status", "route_reason", "labels_json", "target_json"]

    def process(self, inputs: StepInput) -> StepOutput:  # type: ignore[override]
        for row in inputs:
            labels = {t: summarise(row[f"scores_{i}"] or [], row[f"reasons_{i}"] or [])
                      for i, t in enumerate(self.teachers)}
            why = []
            failed = [t for t, l in labels.items() if l["outcome"] == "FAILED"]
            if failed:
                status, why = "auto_reject", [f"no usable sample from {', '.join(failed)}"]
                target = None
            else:
                b = json.loads(row["bundle_json"])
                meds = {t: l["median"] for t, l in labels.items()}
                if max(meds.values()) - min(meds.values()) > self.max_gap:
                    why.append("teachers disagree: " + ", ".join(f"{t} {m}" for t, m in meds.items()))
                for t, l in labels.items():
                    v = [x["score"] for x in l["samples"] if x["valid"]]
                    if max(v) - min(v) > self.max_spread:
                        why.append(f"{t} unstable: samples {v}")
                    why += [f"{t}: {w}" for w in anchor_breaches(b, row["category"], l["median"])]
                status = "manual_review" if why else "auto_accept"
                pooled = [x["score"] for l in labels.values() for x in l["samples"] if x["valid"]]
                counts = Counter(pooled)
                target = {"median": statistics.median_low(pooled),
                          "distribution": {str(v): round(counts.get(v, 0) / len(pooled), 3) for v in range(11)}}
            row.update(status=status, route_reason="; ".join(why), labels_json=json.dumps(labels, ensure_ascii=False),
                       target_json=json.dumps(target))
        yield inputs
