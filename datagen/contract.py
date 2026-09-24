"""What a generated bundle must agree with, copied from the pages that define it.

- Attribute names, value shapes and hard-cap inputs: Confluence "Evidence Bundle Schema"
  (bundle_version 1). The JSON Schema itself is schema/evidence-bundle.schema.json.
- Collection contexts and the availability matrix: Confluence "Agent Attribute Availability —
  Input Contract for Risk Analysis", Parts 2-3. That page predates RC-318, so its `agent_id` row
  is dropped here; `permissions` and `deployment` are not in its matrix and are handled in
  assemble.py from the schema page's notes instead.
- Categories, required inputs and the 0-10 scale: the design doc
  (railxia/docs design/2026-09-03-agent-profiling), which wins wherever the pages disagree.
"""

STATUSES = ("ANSWERED", "ABSENT", "TEMPLATED", "PARTIAL", "BLIND", "FAILED")
TIERS = ("declared", "interrogated", "observed")
AUTHORED_BY = ("subject", "platform", "external", "none")
REASONS = (
    "NO_SOURCE_ACCESS", "NOT_FIRST_PARTY", "SOURCE_OK_NOT_PRESENT", "UNKNOWN_HARNESS",
    "NOT_COLLECTED_BY_PACK", "PRIVATE_STORE", "CODE_CONSTRUCTED", "GATEWAY_MANAGED",
    "ORCHESTRATOR_MANAGED", "PROVIDER_HOSTED", "TEMPLATE_UNRESOLVED", "PARSE_FAILED",
    "SIZE_CAP_EXCEEDED",
)

# The 26 names the schema page says RailMon sends in every bundle.
ATTRIBUTES = (
    "deployment", "image_digest", "harness_identity", "framework_identity", "model_name",
    "inference_endpoint", "mcp_servers_declared", "mcp_servers_observed", "tool_names",
    "tool_capability_envelope", "declared_destinations", "observed_destinations",
    "undeclared_destinations", "credential_inventory", "credential_provenance",
    "in_layer_deleted_secrets", "mounts", "workdir", "user", "permissions", "approval_policy",
    "tool_allow_deny", "sandbox_network_policy", "system_prompt_present", "system_prompt_text",
    "skills_inventory",
)

# Input contract Part 2: which sources each collection context reaches.
CONTEXTS = {
    "A": {"runtime"},
    "B": {"image"},
    "C": {"image", "runtime"},
    "D": {"image", "runtime", "manifest"},
    "E": {"image", "runtime", "manifest", "repo"},
}

# Input contract Part 3. Y reliable, P partial, T often templated, N not available.
MATRIX = {  #                       A    B    C    D    E
    "image_digest":              "Y    Y    Y    Y    Y",
    "harness_identity":          "P    Y    Y    Y    Y",
    "framework_identity":        "P    Y    Y    Y    Y",
    "model_name":                "Y    P    Y    Y    Y",
    "inference_endpoint":        "P    T    Y    Y    Y",
    "mcp_servers_declared":      "P    P    P    P    P",
    "mcp_servers_observed":      "Y    N    Y    Y    Y",
    "tool_names":                "P    P    P    P    P",
    "tool_capability_envelope":  "N    N    N    N    P",
    "declared_destinations":     "P    P    P    Y    Y",
    "observed_destinations":     "Y    N    Y    Y    Y",
    "undeclared_destinations":   "N    N    Y    Y    Y",
    "credential_inventory":      "Y    Y    Y    Y    Y",
    "credential_provenance":     "N    P    Y    Y    Y",
    "in_layer_deleted_secrets":  "N    Y    Y    Y    Y",
    "mounts":                    "Y    N    Y    Y    Y",
    "workdir":                   "Y    Y    Y    Y    Y",
    "user":                      "Y    Y    Y    Y    Y",
    "approval_policy":           "P    P    P    P    P",
    "tool_allow_deny":           "P    P    P    P    P",
    "sandbox_network_policy":    "P    P    P    P    P",
    "skills_inventory":          "P    Y    Y    Y    Y",
    "system_prompt_present":     "P    Y    Y    Y    Y",
}


def availability(attribute: str, context: str) -> str:
    return MATRIX[attribute].split()["ABCDE".index(context)]


# Design doc §4; required inputs are Rail Center's coverage.REQUIRED (a draft there too).
CATEGORIES = {
    "identity": "As whom does it call?",
    "api_access": "What can it call, and how destructive?",
    "data_reach": "What data can it read, and how sensitive is it?",
    "containment": "If one of the first three is wrong, how far does it spread?",
    "data_flow": "What leaves the boundary, and to where?",
    "injection_exposure": "Can untrusted content reach the context, and act once it is there?",
    "grant_exercise_gap": "Does what it does match what it declared?",
    "text_signals": "Does the agent's own text contradict or incriminate its configuration?",
}
# What the labeller is told a category covers. The one-line question alone is what production
# asks, and the 7B teachers read `identity` as "which harness is this" from it. Each guide is the
# design doc's §4 description of the category plus the attribute groups the prototype's SCOPE
# (agent-profiling-demo evaluation/approaches.py) gives it. Only the pilot's two are written.
CATEGORY_GUIDE = {
    "identity": (
        "The principal the gateway is judging: the credentials the agent holds and presents "
        "(credential_inventory, credential_provenance, in_layer_deleted_secrets), the user it runs as "
        "(user), and whether what it is can be pinned down (image_digest, harness_identity, "
        "framework_identity). If it can present itself as something it is not, every other judgement "
        "is about the wrong principal."
    ),
    "containment": (
        "If identity, api_access or data_reach is wrong, how far does the damage spread beyond the agent: "
        "privileged mode, Linux capabilities and a writable root filesystem (permissions), the user it "
        "runs as (user), host paths mounted into it (mounts), network egress limits "
        "(sandbox_network_policy), and guardrails (approval_policy, tool_allow_deny). A privileged "
        "container is the extreme case; broad capability sets, a writable root filesystem and a weak "
        "sandbox are the graded middle."
    ),
}

REQUIRED = {
    "identity": ("credential_inventory", "user"),
    "api_access": ("tool_names",),
    "data_reach": ("mounts", "tool_names"),
    "containment": ("permissions", "user", "mounts"),
    "data_flow": ("observed_destinations",),
    "injection_exposure": ("tool_names", "system_prompt_present"),
    "grant_exercise_gap": ("mcp_servers_declared", "tool_names"),
    "text_signals": ("skills_inventory",),
}


def coverage(bundle: dict, category: str) -> list[str]:
    """Required inputs that leave the category INSUFFICIENT_EVIDENCE: BLIND or FAILED, or missing."""
    attrs = bundle["attributes"]
    return [a for a in REQUIRED[category] if a not in attrs or attrs[a]["status"] in ("BLIND", "FAILED")]
