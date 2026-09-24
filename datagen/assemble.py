"""Scenario + teacher surface -> an evidence bundle, with the blindness a real collector would have.

Generated profiles are complete by construction, so a model trained only on them has no calibrated
behaviour for an unobserved field (generation page, "Generate blindness"). Here every attribute's
status comes from the input contract's availability matrix for the scenario's collection context,
then the gateway-fronted modifier (Part 2), then the rule pack's gaps (schema page). Where the
matrix says P, the status is drawn among the ones that cell allows.

Statuses, reasons, tiers and authored_by use only the closed sets in contract.py.
"""
import random
import re

from datagen.contract import CONTEXTS, availability

EXEC_TOOLS = ["shell.run", "python.exec", "bash.exec"]
SHAPES = {"saas": "atat-***", "cloud": "40-char b64", "db": "postgres://***", "mtls": "pem",
          "api_key": "sk-***", "token": "ghp_***"}
PROVIDERS = ["https://api.openai.com/v1", "https://api.mistral.ai/v1", "https://generativelanguage.googleapis.com"]


def attr(value, status, tier, authored_by=None, reason=None, method=None, note=None) -> dict:
    """One attribute object; optional members left out rather than sent as null (schema Rule 7)."""
    a = {"value": value, "status": status, "tier": tier}
    if status in ("ANSWERED", "PARTIAL", "TEMPLATED"):
        a["authored_by"] = authored_by or "none"  # Rule 4: required here, forbidden elsewhere
    for k, v in (("reason", reason), ("method", method), ("note", note)):
        if v is not None:
            a[k] = v
    return a


def blind(reason, tier="observed", note=None):
    return attr(None, "BLIND", tier, reason=reason, note=note)


def _slug(text: str, fallback: str) -> str:
    s = re.sub(r"[^a-z0-9-]+", "-", str(text).lower()).strip("-")
    return (s or fallback)[:60]


def _hex(rng, n):
    return "".join(rng.choice("0123456789abcdef") for _ in range(n))


def _mounts(kinds, data_dir, agent):
    table = {
        "docker_socket": ("/var/run/docker.sock", "/var/run/docker.sock", "rw"),
        "host_etc": ("/etc", "/host/etc", "ro"),
        "host_root": ("/", "/host", "rw"),
        "data_rw": (data_dir, "/data", "rw"),
        "data_ro": (data_dir, "/reference" if "data_rw" in kinds else "/data", "ro"),
        "run_secrets_ro": (f"/run/secrets/{agent}", "/run/secrets", "ro"),
        "kube_sa_token": ("/var/run/secrets/kubernetes.io/serviceaccount",) * 2 + ("ro",),
        "tmp_scratch": ("tmpfs", "/tmp", "rw"),
    }
    return [dict(zip(("source", "target", "mode"), table[k])) for k in kinds]


def bundle(s: dict, surf: dict, idx: int, rng: random.Random) -> dict:
    ctx, gw = s["context"], s["gateway_fronted"]
    reached = CONTEXTS[ctx]
    runtime, image, manifest = "runtime" in reached, "image" in reached, "manifest" in reached
    window = rng.choice([600, 900, 1320, 1800, 3600])
    agent = _slug(surf.get("agent_name"), "agent")
    ns = _slug(surf.get("namespace"), "default")
    dep = _slug(surf.get("deployment_name"), agent)
    data_dir = str(surf.get("data_dir") or f"/srv/{agent}/data").strip() or f"/srv/{agent}/data"
    workdir = str(surf.get("workdir") or "/app").strip() or "/app"
    tools = [str(t).strip() for t in surf.get("tools", []) if str(t).strip()][: s["n_tools"]] or ["docs.search"]
    exec_tool = rng.choice(EXEC_TOOLS) if s["exec_tool"] else None
    hosts = [str(h).strip().lower() for h in surf.get("destinations", []) if str(h).strip()] or [f"api.{ns}.example.com"]
    creds = [
        {"name": re.sub(r"[^A-Z0-9_]", "_", str(n).upper()) or f"CRED_{i}", **c}
        for i, (n, c) in enumerate(zip(surf.get("credential_names", []), s["credentials"]))
    ]
    A = {}  # attributes, in the schema page's order

    # --- inputs_attempted (Rule 6) ---
    def source(name, ok, miss_reason, tried_when_missing=True):
        if ok:
            return {"attempted": True, "reached": True, **({"window_seconds": window} if name == "runtime" else {})}
        if tried_when_missing:
            return {"attempted": True, "reached": False, "reason": miss_reason}
        return {"attempted": False, "reason": miss_reason}

    inputs = {
        "runtime": source("runtime", runtime, "NO_SOURCE_ACCESS", tried_when_missing=False),
        "image": source("image", image, "NO_SOURCE_ACCESS"),
        "manifest": source("manifest", manifest, "NO_SOURCE_ACCESS", tried_when_missing=rng.random() < 0.5),
        "repo": source("repo", "repo" in reached, "NOT_FIRST_PARTY", tried_when_missing=False),
    }

    # --- deployment (schema page: the closed key set, read from env or labels) ---
    if not runtime:
        A["deployment"] = blind("NO_SOURCE_ACCESS", "declared", "container environment and labels need a running copy")
    elif s["deployment_key"] == "env":
        A["deployment"] = attr({"RAIL_DEPLOYMENT": dep, "RAIL_NAMESPACE": ns}, "ANSWERED", "declared", "platform",
                               method="container environment")
    elif s["deployment_key"] == "compose":
        A["deployment"] = attr({"com.docker.compose.project": ns, "com.docker.compose.service": dep}, "ANSWERED",
                               "declared", "platform", method="container labels")
    else:
        A["deployment"] = attr(None, "ABSENT", "declared", method="no key of the set in container environment or labels")

    # --- identity ---
    A["image_digest"] = attr(f"sha256:{_hex(rng, 64)}", "ANSWERED", "observed", "none")
    custom = s["harness"] == "custom"
    fingerprint = "fingerprint: python3.12 + uvicorn + an agent loop in /app/main.py"
    if custom:
        A["harness_identity"] = blind("UNKNOWN_HARNESS", "declared", fingerprint)
    elif availability("harness_identity", ctx) == "P" and rng.random() < 0.5:
        A["harness_identity"] = blind("NO_SOURCE_ACCESS", "interrogated", "no version endpoint answered")
    else:
        A["harness_identity"] = attr(s["harness"], "ANSWERED", "interrogated" if ctx == "A" else "declared", "subject",
                                     method="queried the harness /version endpoint" if ctx == "A" else "image labels + package manifest")
    if availability("framework_identity", ctx) == "P" and rng.random() < 0.5:
        A["framework_identity"] = blind("NO_SOURCE_ACCESS", "declared", "package manifest is in the image, which was not reached")
    else:
        A["framework_identity"] = attr(s["framework"], "ANSWERED", "declared", "subject", method="package manifest")

    # --- model ---
    model = str(surf.get("model_name") or "gpt-4.1-mini").strip()
    if availability("model_name", ctx) == "P" and rng.random() < 0.5:
        A["model_name"] = blind("TEMPLATE_UNRESOLVED", "declared", "set from an environment variable at deploy time")
    else:
        A["model_name"] = attr(model, "ANSWERED", "observed" if runtime else "declared", "none" if runtime else "subject")
    resolved = rng.choice(PROVIDERS) if s["endpoint_kind"] == "provider" else f"http://llm-gw.{ns}.svc:8080/v1"
    cell = availability("inference_endpoint", ctx)
    if cell == "T" or (s["endpoint_kind"] == "templated" and not runtime):
        A["inference_endpoint"] = attr("${MODEL_ENDPOINT}", "TEMPLATED", "declared", "subject", reason="TEMPLATE_UNRESOLVED")
    elif cell == "P" and rng.random() < 0.4:
        A["inference_endpoint"] = blind("NO_SOURCE_ACCESS", "observed", f"no model traffic in the {window}s window")
    else:
        A["inference_endpoint"] = attr(resolved, "ANSWERED", "observed", "none")

    # --- tool reach ---
    mcp_names = [_slug(n, f"mcp-{i}") for i, n in enumerate(surf.get("mcp_servers", []))] or ["mcp-files"]
    mcp_decl = [{"name": n, "root": "/" if (i == 0 and s["mcp_root_slash"]) else data_dir, "mode": rng.choice(["ro", "rw"])}
                for i, n in enumerate(mcp_names)]
    gw_note = "empty because the gateway holds the list, NOT because there are none. Lower bound is >= 1, not 0."
    if gw:
        A["mcp_servers_declared"] = blind("GATEWAY_MANAGED", "declared", gw_note)
    else:
        r = rng.random()
        if r < 0.5 or s["mcp_root_slash"]:
            A["mcp_servers_declared"] = attr(mcp_decl, "ANSWERED", "declared", "subject", method="parsed .mcp.json")
        elif r < 0.75:
            A["mcp_servers_declared"] = attr(mcp_decl[:1], "PARTIAL", "declared", "subject", reason="CODE_CONSTRUCTED",
                                             method="parsed .mcp.json; servers built in code are not visible")
        else:
            A["mcp_servers_declared"] = blind(rng.choice(["CODE_CONSTRUCTED", "PRIVATE_STORE"]), "declared")
    if not runtime:
        A["mcp_servers_observed"] = blind("NO_SOURCE_ACCESS", "observed", "wire capture needs a running copy")
    elif gw:
        A["mcp_servers_observed"] = attr([{"endpoint": "mcp-gw.internal:7443", "sessions": rng.randint(1, 9), "transport": "http"}],
                                         "PARTIAL", "observed", "none", reason="GATEWAY_MANAGED",
                                         note="sessions to the gateway; upstream servers are not distinguishable")
    else:
        A["mcp_servers_observed"] = attr([{"endpoint": f"{n}.{ns}.svc:7443", "sessions": rng.randint(1, 9), "transport": "http"}
                                          for n in mcp_names], "ANSWERED", "observed", "none")
    all_tools = tools + ([exec_tool] if exec_tool else [])
    if runtime:
        seen = [t for t in all_tools if rng.random() < 0.8] or all_tools[:1]
        A["tool_names"] = attr(seen, "PARTIAL", "observed", "none", method=f"JSON-RPC frames seen during a {window}s window",
                               note="floor, not a count; tools not exercised in the window are absent here")
    else:
        declared = all_tools + ([f"{tools[0].split('.')[0]}.*"] if s["wildcard_tool"] else [])
        A["tool_names"] = attr(declared, "PARTIAL", "declared", "subject", reason="CODE_CONSTRUCTED",
                               method="harness tool config in the image; tools built in code are not visible")
    A["tool_capability_envelope"] = (blind("NOT_COLLECTED_BY_PACK", "declared", "nothing produces it yet")
                                     if "repo" in reached else blind("NOT_FIRST_PARTY", "declared", "repo AST only (context E)"))

    # --- egress ---
    dests = [{"host": h, "tls": rng.random() < 0.85} for h in hosts]
    cell = availability("declared_destinations", ctx)
    if gw:
        A["declared_destinations"] = blind("GATEWAY_MANAGED", "declared")
    elif cell == "Y":
        A["declared_destinations"] = attr(dests, "ANSWERED", "declared", "platform", method="egress policy in the cluster API")
    else:
        r = rng.random()
        if r < 0.4:
            A["declared_destinations"] = attr(dests, "ANSWERED", "declared", "subject", method="hosts in harness config and env")
        elif r < 0.7:
            A["declared_destinations"] = attr(dests[:1], "PARTIAL", "declared", "subject", reason="CODE_CONSTRUCTED",
                                              method="hosts in harness config; hosts built in code are not visible")
        elif r < 0.85:
            A["declared_destinations"] = attr(None, "ABSENT", "declared", method="no hosts declared in harness config or env")
        else:
            A["declared_destinations"] = blind("PRIVATE_STORE", "declared")
    if not runtime:
        A["observed_destinations"] = blind("NO_SOURCE_ACCESS", "observed", "wire capture needs a running copy")
        observed = None
    else:
        observed = [{**d, "peer_guess": rng.choice(["external", "data_service"])} for d in dests if rng.random() < 0.85] or \
                   [{**dests[0], "peer_guess": "external"}]
        if A["inference_endpoint"]["status"] == "ANSWERED":
            host = re.sub(r"^https?://([^/:]+).*$", r"\1", A["inference_endpoint"]["value"])
            observed.append({"host": host, "tls": A["inference_endpoint"]["value"].startswith("https"),
                             "peer_guess": "external" if s["endpoint_kind"] == "provider" else "data_service"})
        A["observed_destinations"] = attr(observed, "ANSWERED", "observed", "none")
    decl = A["declared_destinations"]
    if observed is None:
        A["undeclared_destinations"] = blind("NO_SOURCE_ACCESS", "declared", "NOT COMPUTABLE: needs declared AND observed")
    elif decl["status"] in ("BLIND", "FAILED"):
        A["undeclared_destinations"] = blind(decl["reason"], "declared", "NOT COMPUTABLE: declared side is blind")
    elif decl["status"] == "PARTIAL":
        A["undeclared_destinations"] = blind("CODE_CONSTRUCTED", "declared", "declared side is a floor, so the difference would overcount")
    else:
        known = {d["host"] for d in (decl["value"] or [])}
        A["undeclared_destinations"] = attr([o for o in observed if o["host"] not in known], "ANSWERED", "observed", "none")

    # --- secrets ---
    if gw:
        inv = [{"name": "GW_CLIENT_CERT", "class": "mount", "type": "mtls", "shape": "pem", "sha256": _hex(rng, 4) + "…"}]
        prov_map = {"GW_CLIENT_CERT": "injected"}
        note = "gateway-fronted: the agent holds one gateway credential; upstream credentials sit in the gateway"
    else:
        inv = [{"name": c["name"], "class": c["class"], "type": c["type"], "shape": SHAPES[c["type"]],
                "sha256": _hex(rng, 4) + "…"} for c in creds]
        prov_map = {c["name"]: c["provenance"] for c in creds}
        note = "name + class + hash only; values never collected"
    if inv:
        A["credential_inventory"] = attr(inv, "ANSWERED", "observed", "none", note=note)
    else:
        A["credential_inventory"] = attr(None, "ABSENT", "observed", reason="SOURCE_OK_NOT_PRESENT",
                                         method="scanned env, mounted files and image layers for credential shapes")
    cell = availability("credential_provenance", ctx)
    if not inv:
        A["credential_provenance"] = attr(None, "ABSENT", "observed", method="no credentials found to trace")
    elif cell == "N":
        A["credential_provenance"] = blind("NO_SOURCE_ACCESS", "declared", "baked-vs-injected needs image and runtime together")
    elif cell == "P":
        A["credential_provenance"] = attr({k: v for k, v in prov_map.items() if v == "baked"}, "PARTIAL", "observed", "none",
                                          method="image layers only; injected credentials are not visible")
    else:
        A["credential_provenance"] = attr(prov_map, "ANSWERED", "observed", "none", method="image layers diffed against runtime env")
    if not image:
        A["in_layer_deleted_secrets"] = blind("NO_SOURCE_ACCESS", "observed", "static-only; runtime cannot see image layers")
    elif s["deleted_layer_secret"]:
        layer = rng.randint(2, 6)
        A["in_layer_deleted_secrets"] = attr([{"layer": layer, "name": "DEPLOY_KEY_OLD", "deleted_in_layer": layer + rng.randint(1, 3)}],
                                             "ANSWERED", "observed", "none", note="still present in the registry image")
    else:
        A["in_layer_deleted_secrets"] = attr(None, "ABSENT", "observed", reason="SOURCE_OK_NOT_PRESENT",
                                             method="walked every image layer for deleted secret files")

    # --- filesystem & privilege ---
    mounts = _mounts(s["mounts"], data_dir, agent)
    if availability("mounts", ctx) == "N":
        A["mounts"] = blind("NO_SOURCE_ACCESS", "declared", "mounts are set at run time; nothing is running")
    elif not mounts:
        A["mounts"] = attr(None, "ABSENT", "observed", method="container inspect: no bind or volume mounts")
    elif manifest:
        A["mounts"] = attr(mounts, "ANSWERED", "declared", "platform", method="pod spec volumeMounts, read from the cluster API")
    else:
        A["mounts"] = attr(mounts, "ANSWERED", "observed", "none", method="container inspect")
    A["workdir"] = attr(workdir, "ANSWERED", "observed" if runtime else "declared", "none" if runtime else "subject")
    user = "root" if s["run_as"] == "root" else rng.choice(["app", "node", "agent", "1000:1000", "nobody"])
    A["user"] = attr(user, "ANSWERED", "observed" if runtime else "declared", "none" if runtime else "subject")
    perms = {"privileged": s["privileged"], "caps": s["caps"], "root_fs": s["root_fs"]}
    if s["rule_pack_version"] == 14:
        A["permissions"] = blind("NOT_COLLECTED_BY_PACK", "observed", "privileged flag / Linux caps are P1; pack 14 has no collector")
    elif not (runtime or manifest):
        A["permissions"] = blind("NO_SOURCE_ACCESS", "observed", "privileged flag and caps are run-time properties")
    elif manifest:
        A["permissions"] = attr(perms, "ANSWERED", "declared", "platform", method="pod securityContext, read from the cluster API")
    else:
        A["permissions"] = attr(perms, "ANSWERED", "observed", "none", method="container inspect HostConfig")

    # --- guardrails (P everywhere: sparse) ---
    if gw:
        A["approval_policy"] = blind("GATEWAY_MANAGED", "declared", "absence is NOT evidence of restriction; assume no approval gate")
        A["tool_allow_deny"] = blind("GATEWAY_MANAGED", "declared")
    else:
        r = rng.random()
        if s["approval_gate"]:
            A["approval_policy"] = (attr({"destructive_requires_approval": True}, "ANSWERED", "declared", "subject", method="harness config")
                                    if r < 0.6 else blind("PRIVATE_STORE", "declared", "absence is NOT evidence of restriction"))
        elif r < 0.3:
            A["approval_policy"] = attr({"destructive_requires_approval": False}, "ANSWERED", "declared", "subject", method="harness config")
        elif r < 0.7:
            A["approval_policy"] = attr(None, "ABSENT", "declared", reason="SOURCE_OK_NOT_PRESENT", method="checked harness config for an approval block")
        else:
            A["approval_policy"] = blind("PRIVATE_STORE", "declared", "absence is NOT evidence of restriction")
        r = rng.random()
        if r < 0.35:
            A["tool_allow_deny"] = attr({"allow": tools, "deny": []}, "ANSWERED", "declared", "subject", method="harness config")
        elif r < 0.7:
            A["tool_allow_deny"] = attr(None, "ABSENT", "declared", reason="SOURCE_OK_NOT_PRESENT", method="checked harness config for allow/deny lists")
        else:
            A["tool_allow_deny"] = blind("PRIVATE_STORE", "declared")
    if rng.random() < 0.25:
        A["sandbox_network_policy"] = blind("NO_SOURCE_ACCESS", "observed")
    elif s["network_policy"] == "none":
        A["sandbox_network_policy"] = attr(None, "ABSENT", "observed", reason="SOURCE_OK_NOT_PRESENT",
                                           method="checked harness sandbox block + container network mode")
    elif s["network_policy"] == "egress-allowlist":
        A["sandbox_network_policy"] = attr("egress allow-list: " + ", ".join(hosts), "ANSWERED", "declared", "subject",
                                           method="harness sandbox block")
    else:
        A["sandbox_network_policy"] = attr("default: allow all egress", "ANSWERED", "observed", "none", method="container network mode")

    # --- content ---
    if availability("system_prompt_present", ctx) == "P" and rng.random() < 0.5:
        A["system_prompt_present"] = blind("NOT_COLLECTED_BY_PACK", "observed")
    else:
        A["system_prompt_present"] = attr(s["system_prompt"], "ANSWERED", "observed", "subject", note="presence only")
    A["system_prompt_text"] = blind("NOT_COLLECTED_BY_PACK", "observed")
    skills = [{"name": _slug(k.get("name"), f"skill-{i}"), "description": str(k.get("description", "")).strip(),
               "source_type": "skills_config",
               "destination_endpoints": [str(e) for e in k.get("destination_endpoints", [])][:3]}
              for i, k in enumerate(surf.get("skills", [])[: s["n_skills"]])]
    if availability("skills_inventory", ctx) == "P" and rng.random() < 0.5:
        A["skills_inventory"] = blind("NO_SOURCE_ACCESS", "declared", "skills config is in the image, which was not reached")
    elif not skills:
        A["skills_inventory"] = attr(None, "ABSENT", "declared", method="no SKILL.md or skills config found")
    else:
        A["skills_inventory"] = attr(skills, "ANSWERED", "declared", "subject",
                                     method="SKILL.md frontmatter; skills constructed in code are not visible")

    return {
        "bundle_version": 1,
        "bundle_id": f"bnd-syn-{idx:04d}-{_hex(rng, 6)}",
        "host_id": f"host-{_hex(rng, 8)}",
        "sandbox_name": agent,
        "collected_at": f"2026-09-{rng.randint(1, 23):02d}T{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}Z",
        "rule_pack_version": s["rule_pack_version"],
        "inputs_attempted": inputs,
        "attributes": A,
    }
