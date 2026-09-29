"""The open-weight teachers, served locally by Ollama.

Open-weight only: the data generation page (§3) and the design doc both rule out training on a
commercial model's outputs. Two teachers from different families, mixed (§3.1), because mixing
two similarly biased teachers barely helps.
"""
import json
import os
import time
import urllib.request
from pathlib import Path

OLLAMA_HOST = "http://localhost:11434"
# Mac mini M4 Pro, 48 GB (from 2026-09-28): the strongest open-weight models that fit, one per
# vendor. Both licences are plain Apache-2.0, so their outputs may train another model.
TEACHERS = {
    "qwen3.8:27b": "Apache-2.0, Alibaba Qwen",
    "gemma4:31b": "Apache-2.0, Google",
}
if os.environ.get("DATAGEN_TEACHERS"):  # e.g. "qwen2.5:7b,mistral-nemo" for a quick check on small models
    TEACHERS = {m: "set by DATAGEN_TEACHERS" for m in os.environ["DATAGEN_TEACHERS"].split(",")}
GEN_MIX = dict(zip(TEACHERS, (0.7, 0.3)))  # generation page §3.1: mix in a different teacher
# The first pilot's teachers (2026-09-24), sized for a 16 GB MacBook Air. Its data in data/ used these.
PILOT = {
    "qwen2.5:7b": "Apache-2.0, Alibaba Qwen",
    "mistral-nemo": "Apache-2.0, Mistral AI / NVIDIA",
    "qwen3:14b": "Apache-2.0, Alibaba Qwen",
}
CALL_LOG: str | None = None  # set by a runner to record every call's timing
# Ollama 0.33.3 serves Qwen 3.8's architecture (qwen35) one request at a time: "model architecture
# does not currently support parallel requests". Sending it more only queues them, and interleaved
# bundles evict each other's cached prefix, so a concurrent runner sends one at a time.
SLOTS = {"qwen3.8:27b": 1}


def think_setting(model: str) -> bool | None:
    """Thinking multiplies the output several times over; off for throughput where the model allows it."""
    return False if model.startswith(("qwen3", "gemma4")) else None


def log_call(path: str | None, stage: str, model: str, t0: float, t1: float, resp: dict, error: str | None) -> None:
    """One line per call: wall time, and Ollama's own split into loading, prompt and generation."""
    if not path:
        return
    s = lambda k: round(resp.get(k, 0) / 1e9, 3)  # noqa: E731 -- Ollama reports nanoseconds
    rec = {"stage": stage, "model": model, "start": round(t0, 3), "end": round(t1, 3), "wall_s": round(t1 - t0, 3),
           "load_s": s("load_duration"), "prompt_tokens": resp.get("prompt_eval_count", 0), "prompt_s": s("prompt_eval_duration"),
           "output_tokens": resp.get("eval_count", 0), "output_s": s("eval_duration"), **({"error": error} if error else {})}
    with Path(path).open("a") as f:
        f.write(json.dumps(rec) + "\n")


def chat(model: str, system: str, user: str, schema: dict, temperature: float, seed: int | None = None,
         stage: str = "") -> dict:
    """One call; returns the parsed JSON reply, or {"_error": ...} when it is not valid JSON."""
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "format": schema,
        "stream": False,
        "options": {"temperature": temperature, "num_ctx": 8192, **({"seed": seed} if seed is not None else {})},
    }
    if think_setting(model) is not None:
        body["think"] = think_setting(model)
    req = urllib.request.Request(f"{OLLAMA_HOST}/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        resp = json.loads(r.read())
    log_call(CALL_LOG, stage, model, t0, time.time(), resp, None)
    content = resp["message"]["content"]
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        return {"_error": f"invalid JSON: {e}", "_raw": content[:500]}
