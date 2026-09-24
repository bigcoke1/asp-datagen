"""The teacher writes the surface of a scenario: the names and text a real bundle would carry.

It is told the domain, the job, the harness and how many of each thing to write. It is never told
a risk level or anything that implies one (generation page §1), and `guard` refuses to send a
prompt that slips a risk word in, since a single "overprivileged" writes the label.
"""
import re

from datagen.llm import chat

# Words that name or imply a risk level. A generation prompt carrying one is refused.
_RISK_WORDS = re.compile(
    r"\b(risk|safe|unsafe|danger|secur|insecur|vulnerab|privileg|overprivileg|critical|exposure|"
    r"attack|malicious|complian|threat|harm|breach|exploit|audit)", re.I)

SYSTEM = (
    "You write realistic configuration details for fictional AI agent deployments. The output is "
    "test data for a scanner. Be concrete and varied: real-looking hostnames, environment variable "
    "names, tool identifiers in dotted form (service.resource.action), and one-sentence skill "
    "descriptions in the voice of the team that wrote them. Return only the JSON asked for."
)


def guard(prompt: str) -> str:
    hit = _RISK_WORDS.search(prompt)
    if hit:
        raise ValueError(f"generation prompt names a risk level via {hit.group(0)!r}: {prompt[:120]}")
    return prompt


def _schema(s: dict) -> dict:
    str_list = lambda n: {"type": "array", "items": {"type": "string"}, "minItems": n, "maxItems": n}
    return {
        "type": "object",
        "required": ["agent_name", "workdir", "data_dir", "model_name", "tools", "credential_names",
                     "destinations", "skills", "mcp_servers", "deployment_name", "namespace"],
        "properties": {
            "agent_name": {"type": "string"},
            "workdir": {"type": "string"},
            "data_dir": {"type": "string"},
            "model_name": {"type": "string"},
            "tools": str_list(s["n_tools"]),
            "credential_names": str_list(len(s["credentials"])),
            "destinations": str_list(s["n_destinations"]),
            "skills": {"type": "array", "minItems": s["n_skills"], "maxItems": s["n_skills"], "items": {
                "type": "object", "required": ["name", "description", "destination_endpoints"],
                "properties": {"name": {"type": "string"}, "description": {"type": "string"},
                               "destination_endpoints": {"type": "array", "items": {"type": "string"}}}}},
            "mcp_servers": str_list(2),
            "deployment_name": {"type": "string"},
            "namespace": {"type": "string"},
        },
    }


def prompt(s: dict) -> str:
    creds = ", ".join(c["type"] for c in s["credentials"]) or "none"
    return guard(
        f"An AI agent in {s['domain']} whose job is to {s['job']}. It runs on {s['harness']}.\n"
        f"Write:\n"
        f"- agent_name: a short kebab-case name for it\n"
        f"- workdir: its working directory inside the container\n"
        f"- data_dir: the host directory holding the data it works on\n"
        f"- model_name: the LLM it calls\n"
        f"- tools: exactly {s['n_tools']} tool identifiers it would use for this job\n"
        f"- credential_names: exactly {len(s['credentials'])} environment variable names, one for "
        f"each of these credential kinds in order: {creds}\n"
        f"- destinations: exactly {s['n_destinations']} hostnames it talks to\n"
        f"- skills: exactly {s['n_skills']} skills, each with a name, a one-sentence description, and "
        f"the hostnames it sends to (may be empty)\n"
        f"- mcp_servers: 2 MCP server names it might use\n"
        f"- deployment_name and namespace: what its operators call the deployment and namespace"
    )


def surface(s: dict, teacher: str, seed: int) -> dict:
    out = chat(teacher, SYSTEM, prompt(s), _schema(s), temperature=0.9, seed=seed)
    if "_error" in out:
        raise RuntimeError(f"{teacher} returned no usable surface: {out['_error']}")
    return out
