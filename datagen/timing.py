"""Where a run's time went, from the per-call log (`calls.jsonl`) that `llm.log_call` writes.

Writes timing.json and timing.md beside the run's output. "Active" is the union of call
intervals, so calls running side by side are not counted twice. Ollama's prompt token count
includes the cached prefix, so prompt cost is reported as time rather than as tokens per second.
"""
import json
import platform
import statistics
import subprocess
import urllib.request
from pathlib import Path

from datagen.llm import OLLAMA_HOST


def _union(intervals: list[tuple[float, float]]) -> float:
    total, end = 0.0, float("-inf")
    for a, b in sorted(intervals):
        if b > end:
            total += b - max(a, end)
            end = b
    return total


def machine(models: list[str]) -> dict:
    """What the run ran on, so the numbers can be read against the hardware."""
    sysctl = lambda k: subprocess.run(["sysctl", "-n", k], capture_output=True, text=True).stdout.strip()  # noqa: E731
    get = lambda p, body=None: json.loads(urllib.request.urlopen(urllib.request.Request(  # noqa: E731
        OLLAMA_HOST + p, data=json.dumps(body).encode() if body else None), timeout=30).read())
    info = {"chip": sysctl("machdep.cpu.brand_string"), "memory_gb": round(int(sysctl("hw.memsize") or 0) / 2**30),
            "macos": platform.mac_ver()[0], "ollama": get("/api/version")["version"], "models": {}}
    for m in models:
        d = get("/api/show", {"model": m}).get("details", {})
        info["models"][m] = f"{d.get('parameter_size')} {d.get('quantization_level')}"
    return info


def summarise(out: Path, wall_s: float, n_bundles: int, meta: dict) -> dict:
    calls = [json.loads(line) for line in (out / "calls.jsonl").open() if line.strip()]
    groups: dict[tuple[str, str], list[dict]] = {}
    for c in calls:
        groups.setdefault((c["stage"], c["model"]), []).append(c)
    stages = []
    for (stage, model), cs in sorted(groups.items(), key=lambda kv: min(c["start"] for c in kv[1])):
        lat = sorted(c["wall_s"] for c in cs)
        stages.append({
            "stage": stage, "model": model, "calls": len(cs), "errors": sum("error" in c for c in cs),
            "active_s": round(_union([(c["start"], c["end"]) for c in cs]), 1),
            "latency_median_s": round(statistics.median(lat), 1), "latency_p95_s": round(lat[int(0.95 * (len(lat) - 1))], 1),
            "prompt_s": round(sum(c["prompt_s"] for c in cs), 1),
            "output_tokens": sum(c["output_tokens"] for c in cs), "output_s": round(sum(c["output_s"] for c in cs), 1),
            "model_loads": sum(c["load_s"] > 1 for c in cs), "load_s": round(sum(c["load_s"] for c in cs), 1),
        })
    active = _union([(c["start"], c["end"]) for c in calls])
    result = {
        **meta, "wall_s": round(wall_s, 1), "bundles": n_bundles, "calls": len(calls),
        "llm_active_s": round(active, 1), "outside_llm_s": round(wall_s - active, 1),
        "s_per_bundle": round(wall_s / max(n_bundles, 1), 1),
        "hours_per_1000_bundles": round(wall_s / max(n_bundles, 1) * 1000 / 3600, 1),
        "stages": stages,
    }
    (out / "timing.json").write_text(json.dumps(result, indent=2))
    (out / "timing.md").write_text(render(result))
    return result


def _dur(s: float) -> str:
    return f"{s / 60:.1f} min" if s >= 90 else f"{s:.0f} s"


def render(t: dict) -> str:
    m = t.get("machine", {})
    lines = [f"# Timing: {t.get('pipeline', '')}", "",
             f"- Machine: {m.get('chip')}, {m.get('memory_gb')} GB, macOS {m.get('macos')}, Ollama {m.get('ollama')}",
             "- Models: " + ", ".join(f"`{k}` ({v})" for k, v in m.get("models", {}).items()),
             f"- Settings: {t.get('settings', '')}",
             f"- **{t['bundles']} bundles in {_dur(t['wall_s'])}**: {t['s_per_bundle']:.0f} s per bundle, "
             f"so about {t['hours_per_1000_bundles']} h per 1,000 bundles at these settings.",
             f"- LLM calls: {t['calls']}. Time with at least one call running: {_dur(t['llm_active_s'])}; "
             f"with none: {_dur(t['outside_llm_s'])}.", "",
             "| stage | model | calls | active | median call | p95 call | prompt time | output tokens | output time | model loads |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for s in t["stages"]:
        failed = f" ({s['errors']} failed)" if s["errors"] else ""
        lines.append(f"| {s['stage']} | `{s['model']}` | {s['calls']}{failed} | "
                     f"{_dur(s['active_s'])} | {s['latency_median_s']} s | {s['latency_p95_s']} s | {_dur(s['prompt_s'])} | "
                     f"{s['output_tokens']:,} | {_dur(s['output_s'])} | {s['model_loads']} ({s['load_s']:.0f} s) |")
    return "\n".join(lines) + "\n"
