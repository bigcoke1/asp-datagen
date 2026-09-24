"""The open-weight teachers, served locally by Ollama.

Open-weight only: the data generation page (§3) and the design doc both rule out training on a
commercial model's outputs. Two teachers from different families, mixed (§3.1), because mixing
two similarly biased teachers barely helps.
"""
import json
import urllib.request

OLLAMA = "http://localhost:11434/api/chat"
TEACHERS = {
    "qwen2.5:7b": "Apache-2.0, Alibaba Qwen",
    "mistral-nemo": "Apache-2.0, Mistral AI / NVIDIA",
}


def chat(model: str, system: str, user: str, schema: dict, temperature: float, seed: int | None = None) -> dict:
    """One call; returns the parsed JSON reply, or {"_error": ...} when it is not valid JSON."""
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "format": schema,
        "stream": False,
        "options": {"temperature": temperature, "num_ctx": 8192, **({"seed": seed} if seed is not None else {})},
    }
    req = urllib.request.Request(OLLAMA, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        content = json.loads(r.read())["message"]["content"]
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        return {"_error": f"invalid JSON: {e}", "_raw": content[:500]}
