"""Sample one scenario: the facts a bundle will state, chosen by code rather than by a teacher.

Every fact that bears on a risk score is drawn here, spread evenly across its possible values, so
the corpus spans the spectrum by construction (generation page §7, class balance) without anyone
naming a risk level (§1). The teacher later writes only the surface a real bundle would carry —
names, tools, skill text, hosts — and never sees these facts described as good or bad.

The scenario is kept beside the bundle for auditing and is never shown to a labeller.
"""
import random

DOMAINS = [
    ("fintech", "reconcile ledger exports against bank statements"),
    ("healthcare", "summarise patient intake forms for clinicians"),
    ("devops", "triage failing CI pipelines and open fix branches"),
    ("e-commerce", "answer order status questions from customers"),
    ("legal", "compare contract clauses against a playbook"),
    ("human resources", "screen job applications and schedule interviews"),
    ("marketing", "draft and schedule social media posts"),
    ("SOC operations", "enrich alert tickets with indicator lookups"),  # named so the guard passes
    ("data engineering", "run and monitor nightly warehouse jobs"),
    ("customer support", "sync support tickets with the issue tracker"),
    ("research", "search literature and summarise papers"),
    ("internal IT", "handle account unlock and access requests"),
    ("logistics", "update shipment ETAs from carrier feeds"),
    ("education", "grade quizzes and write feedback"),
    ("insurance", "extract fields from claim documents"),
    ("media", "transcribe and tag uploaded videos"),
    ("manufacturing", "read sensor dashboards and file maintenance orders"),
    ("public sector", "route records requests to departments"),
]
HARNESSES = [
    ("openclaw/1.8.2", "langgraph/0.2.61"),
    ("claude-code/2.1.252", "node/v24.20.0"),
    ("crewai/0.86.0", "crewai/0.86.0"),
    ("autogen/0.4.7", "autogen-agentchat/0.4.7"),
    ("custom", "fastapi/0.115.6"),
]
# Input contract Part 9: the real mix of contexts is unmeasured; these weights are a guess.
CONTEXT_WEIGHTS = {"A": 0.25, "B": 0.10, "C": 0.25, "D": 0.30, "E": 0.10}
MOUNT_KINDS = ["docker_socket", "host_etc", "host_root", "data_rw", "data_ro", "run_secrets_ro",
               "kube_sa_token", "tmp_scratch"]
CAPS = [[], ["NET_BIND_SERVICE"], ["NET_ADMIN", "SYS_PTRACE"], ["SYS_ADMIN"], ["ALL"]]
CRED_TYPES = ["saas", "cloud", "db", "mtls", "api_key", "token"]
CRED_CLASSES = ["secret_plaintext", "secret_ref", "mount"]


def sample(rng: random.Random) -> dict:
    context = rng.choices(list(CONTEXT_WEIGHTS), weights=list(CONTEXT_WEIGHTS.values()))[0]
    domain, job = rng.choice(DOMAINS)
    harness, framework = rng.choice(HARNESSES)
    n_creds = rng.randint(0, 4)
    return {
        "domain": domain,
        "job": job,
        "harness": harness,
        "framework": framework,
        "context": context,
        "gateway_fronted": rng.random() < 0.10,  # input contract Part 9: "5-10% and rising"
        # Pack 14 has no permissions collector (schema page). Pack 15 is ASSUMED to have one, so
        # that containment, which requires permissions, is ever evaluable. No such pack exists yet.
        "rule_pack_version": rng.choice([14, 15, 15]),
        "run_as": rng.choice(["root", "non_root"]),
        "privileged": rng.random() < 0.25,
        "caps": rng.choice(CAPS),
        "root_fs": rng.choice(["read-only", "read-write"]),
        "mounts": sorted(rng.sample(MOUNT_KINDS, rng.randint(0, 3))),
        "credentials": [
            {"type": rng.choice(CRED_TYPES), "class": rng.choice(CRED_CLASSES),
             "provenance": "baked" if rng.random() < 0.3 else "injected"}
            for _ in range(n_creds)
        ],
        "deleted_layer_secret": rng.random() < 0.2,
        "n_tools": rng.randint(1, 6),
        "exec_tool": rng.random() < 0.35,
        "wildcard_tool": rng.random() < 0.05,
        "mcp_root_slash": rng.random() < 0.05,
        "approval_gate": rng.choice([True, False]),
        "network_policy": rng.choice(["none", "egress-allowlist", "default-allow"]),
        "endpoint_kind": rng.choice(["provider", "internal_gateway", "templated"]),
        "n_destinations": rng.randint(1, 4),
        "n_skills": rng.randint(0, 3),
        "system_prompt": rng.random() < 0.8,
        "deployment_key": rng.choice(["env", "compose", "none"]),
    }
