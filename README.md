# asp-datagen

Synthetic training data for agent security profiling. The pipeline generates evidence bundles and has open-weight teachers label them per risk category. The labelled pairs are what a fine-tuned scorer such as [Laya](https://huggingface.co/convaiinnovations/laya) trains on.

It follows the **Synthetic Training Data Generation Pipeline** page (Confluence `AgBAAg`) for method. Where that page is stale, the design doc in `railxia/docs` (`design/2026-09-03-agent-profiling`) wins.

Two drivers run the same steps:
- **`datagen.run`:** plain Python.
- **`datagen.distil_run`:** a [distilabel](https://github.com/argilla-io/distilabel) DAG with a routing gateway at the end. It is a trial of an older prototype. [Distilabel: what it bought and what it cost](#distilabel-what-it-bought-and-what-it-cost) has the verdict, and [the timing](#timing) is measured on this machine.

## Pipeline

```
scenarios.py   code samples the facts            run as root? mounts? privileged? credential class and provenance?
     │         spread evenly, never labelled      context A-E, gateway-fronted, rule pack
     ▼
generate.py    a teacher writes the surface       names, tools, hosts, skill text; no risk words (guarded)
     ▼
assemble.py    facts + surface → bundle           statuses from the input contract's availability matrix
     ▼
validate.py    Evidence Bundle Schema             JSON Schema (Draft 2020-12) + Rule 5 + all 26 attributes
     ▼
label.py       open-weight teachers, k samples    sees only the bundle; 0-10, 10 safest; coverage-gated
     ▼
distil.py      gateway (distil_run only)          auto_accept · manual_review (review.csv) · auto_reject
```

## Rules it follows, and where each comes from

| Rule | Source | How |
|---|---|---|
| Never name the risk level when generating | Generation page §1 | Code samples facts evenly across their values. The teacher is told only the domain, job, harness and counts, and `generate.guard` refuses any prompt that contains a risk word. |
| Class balance | Generation page §7 | Balance comes from how facts are sampled, not from labels. It does not survive labelling yet (see Results). |
| Open-weight teachers, two of them, mixed | Generation page §3, design doc | `qwen3.8:27b` (Alibaba) and `gemma4:31b` (Google), both Apache-2.0, served locally by Ollama. Generation mixes them 70/30, and both label every bundle. Pilot 1 used `qwen2.5:7b` and `mistral-nemo`, with `qwen3:14b` as a larger labeller. |
| Generate blindness, not just configuration | Generation page (update), design doc | Each attribute's status follows the input contract's matrix for contexts A-E, plus the gateway-fronted modifier and the rule pack's gaps. |
| Closed enums only | Evidence Bundle Schema page | Every bundle is validated against `schema/evidence-bundle.schema.json`, which is the page's schema as copied into Rail Center's test vectors. |
| Blind labelling | Generation page §1 | The labeller sees the bundle and nothing else. The scenario is kept in `data/scenarios.jsonl` for audit. |
| A category with blind required inputs is not scored | Design doc §4 (coverage profiler) | These get `INSUFFICIENT_EVIDENCE`, and the teacher is not asked. |
| 0-10 scale, 10 safest | Design doc | The rubric is the prototype's `STATES` + `SCALE_V2`. |

## Who wrote what in a bundle

This matters for the design doc's rule that training data may not come from a commercial model.

| Part of the bundle | Written by |
|---|---|
| Every fact that bears on risk (user, privileged, caps, root filesystem, mounts, credential class and provenance, deleted-layer secrets, approval gate, network policy, tool count, exec and wildcard tools), and every `status`, `reason`, `tier` and `authored_by` | Python in this repo, seeded random sampling (`scenarios.py`, `assemble.py`) |
| Fixed text strings: every `method` and `note`, mount paths, credential shapes, provider URLs, the harness fingerprint, and the domain and job list | Hard-coded in `assemble.py` and `scenarios.py`. These were written with Claude while building the pipeline. They are templates, not generated per bundle, but they appear in every bundle; check them with legal, or rewrite them, before training on this data. |
| Surface: agent name, workdir, data directory, model name, tool names, credential variable names, hostnames, skill names and descriptions, MCP server names, deployment and namespace | An open-weight teacher, per bundle (`generate.py`). Pilot 1: 15 by `qwen2.5:7b`, 5 by `mistral-nemo`. Pilot 2: 15 by `qwen3.8:27b`, 5 by `gemma4:31b`, in each run |
| Every label (score, reason, distribution) | Open-weight teachers only (`label.py`) |

## Results: pilot 2 (2026-09-29, Mac mini)

**Stronger teachers fix containment's anchors, but they split on identity. A 20-bundle set takes 82 minutes on this machine.**
- **Containment:** both new teachers score bundles with host control at 1–2, with one exception. Unlike pilot 1's teachers, they also score the graded middle: Linux capabilities, a writable root filesystem, open egress.
- **Identity:** the two teachers disagree about whether host control is an identity failure. `qwen3.8:27b` also gives unstable samples.
- **Throughput:** 82 minutes is about 4 minutes per bundle, or 68 hours per 1,000 bundles.
- **Distilabel against plain Python:** distilabel was 18% faster. All of the gain came from running one teacher at a time, which a reordered plain loop would get too. Sending calls concurrently made this machine slower.

### Setup

- **Machine:** Mac mini with an M4 Pro (12-core CPU, 16-core GPU) and 48 GB of memory.
  - Ollama 0.33.3 with stock settings, one request at a time.
  - Ollama lets the GPU use 37.4 GiB, so the two teachers never fit in memory together.
- **Teachers:** `qwen3.8:27b` (Alibaba, 17.7 GB at Q4_K_M) and `gemma4:31b` (Google, 19.9 GB at Q4_K_M).
  - Both are Apache-2.0, and each is its vendor's strongest model that fits, by published benchmarks.
  - Thinking is off.
- **Batch:** the same 20 scenarios as pilot 1 (seed 20260924).
  - Statuses, reasons and facts match pilot 1 bundle for bundle. Only the surface text is new.
  - `qwen3.8:27b` wrote 15 surfaces and `gemma4:31b` wrote 5.
- **Labelling:** pilot 1's prompts and guides, unchanged. Each teacher scored `identity` and `containment` 3 times at temperature 0.7.
- **Two runs of the same job:**
  - Once through `datagen.run` (plain Python) and once through `datagen.distil_run` (distilabel).
  - Each started from a freshly restarted Ollama.
  - No other client used Ollama during either run; this was checked against the server's request log.

### Timing

**Generating and labelling 20 bundles took 82 minutes through distilabel and 100 minutes through plain Python.**

| | plain Python (`datagen.run`) | distilabel (`datagen.distil_run`) |
|---|---|---|
| 20 bundles, wall clock | **99.9 min** | **81.5 min** |
| per bundle | 300 s | 244 s |
| 1,000 bundles, projected | 83 h (3.5 days) | 68 h (2.8 days) |
| model calls | 212 | 212 |
| model loads | 64 (5.4 min) | 3 (22 s) |
| label calls that re-read the whole bundle | 64 of 192 (42.7 min) | 52 of 192 (28.6 min) |
| time outside model calls | under 1 s | 8 s |

A run is 20 generation calls plus 192 label calls. The 192 are 20 bundles × 2 categories × 2 teachers × 3 samples, less the 8 bundle-categories that are `INSUFFICIENT_EVIDENCE` and never reach a teacher.

**Where the time went, distilabel run** (`data/pilot2/distilabel/timing.md`):

| stage | model | calls | time | median call | output |
|---|---|---|---|---|---|
| write surfaces | `qwen3.8:27b` | 15 | 13.8 min | 55 s | 4,769 tokens |
| write surfaces | `gemma4:31b` | 5 | 3.2 min | 42 s | 1,809 tokens |
| label | `gemma4:31b` | 96 | 22.3 min | 5.3 s | 4,974 tokens |
| label | `qwen3.8:27b` | 96 | 42.1 min | 19.5 s | 8,742 tokens |

**Each teacher on this machine:**

| | `qwen3.8:27b` | `gemma4:31b` |
|---|---|---|
| first call on a bundle (reads about 3.4k tokens) | about 50 s, reading 95 tokens/s | about 50 s, reading 76 tokens/s |
| each further call on the same bundle | 16 s | 5 s |
| writing speed | 5.4 tokens/s | 10.7 tokens/s |
| tokens per label (score and reason) | 91 | 52 |
| labelling time per bundle | 126 s | 67 s |
| requests at once, Ollama 0.33.3 | 1 | 4, but slower (below) |

**What the numbers say:**
- **`qwen3.8:27b` is the bottleneck.** It takes 69% of the run. It writes at half `gemma4:31b`'s speed, and its reasons are 75% longer.
- **Reading the bundle is the other large cost.** A cold read takes about 45 s. The pipeline's job is to make each teacher read each bundle once.
- **Distilabel's 18% came from order, not from concurrency.**
  - Its load groups run one teacher at a time: 3 model loads instead of 64.
  - Its rows arrive grouped by bundle, so each teacher reads each bundle about once.
  - The plain loop alternates teachers on every category. So it reloads a model and re-reads the bundle each time.
  - Reordering that loop would get the same saving without distilabel.
- **Concurrency made this machine slower.**
  - With 4 calls in flight, a `gemma4:31b` label call took a median 206 s, instead of 5–50 s. Each of the 4 slots reads its own bundle, reading is compute-bound, and writing stalls behind it (`data/pilot2/aborted-parallel4/`).
  - `qwen3.8:27b` cannot run in parallel at all on this Ollama.
  - Both timed runs above send one call at a time.
- **At this rate a corpus takes days.** 1,000 bundles is about 3 days of continuous running. None of these ways to cut it has been tried here:
  - **Upgrade Ollama to 0.34.4.** Its release notes say "Qwen 3.8 prompt processing is faster on Apple Silicon". It was not upgraded because another project shares this Ollama.
  - **Use the MoE siblings `gemma4:26b` and `qwen3.6:35b`.** They are faster but weaker.
  - **Take 2 samples instead of 3.**
  - **Move to a GPU server with vLLM**, where batched decoding does pay.
- **Against pilot 1:** on the M3 Air, one bundle took 90 s to label with `qwen3:14b`. Here it takes 126 s with `qwen3.8:27b` and 67 s with `gemma4:31b`.

### Do the labels follow the facts?

This is pilot 1's check, run on the distilabel run's labels (`python -m datagen.check --data data/pilot2/distilabel`). Pilot 1's best teacher is shown for reference. The plain run's labels give the same picture.

| check | qwen3:14b (pilot 1) | qwen3.8:27b | gemma4:31b |
|---|---|---|---|
| containment: host reach visible vs not (should be much lower) | 3.3 vs 7.8 | 2.0 vs 4.2 | 1.0 vs 3.3 |
| containment: privileged + root scored ≤ 2 (the anchor is 1) | 1/2 | **2/2** | **2/2** |
| identity: a baked credential visible vs not (should be lower) | 8.2 vs 8.0 ✗ | 4.6 vs 5.5 | 3.2 vs 4.5 |
| identity: no credentials vs some (should be higher) | 9.2 vs 7.8 | 7.5 vs 4.8 | **9.0 vs 3.0** |
| spread across a teacher's own 3 samples | 0.47 | 1.94 ✗ | **0.12** |
| same median in both pilot 2 runs (same facts, new names) | — | 14/32 (27/32 within 1) | **25/32** (30/32 within 1) |

The two teachers' medians land within 1 point of each other on 8/20 bundles for `identity` and 9/12 for `containment`.

**Containment is close to usable, from both teachers.**
- Bundles with host control score 1–2 from both, and both hit the privileged + root anchor. The one exception is 0007 (host `/` mounted, root, caps `ALL`), which `qwen3.8:27b` scored 5.
- They also score the graded middle, which the design doc says is what containment is for once the hard caps take the extreme cases.
  - Bundle 0005 runs as non-root, with `caps: [ALL]`, a writable root filesystem and `bash.exec`, and no approval gate observed.
  - Pilot 1's `qwen3:14b` scored it 8. Both new teachers score it 3, and their reasons cite exactly those attributes.
- `check.py` does not know about capabilities. So its "no host reach" group includes bundles like 0005, which is why the second number in its first row is low.

**Identity splits the teachers, on a question the guide does not answer.**
- Both teachers score an agent with no credentials well above one holding some (9.0 vs 3.0, and 7.5 vs 4.8). A visible baked credential pulls the score down, but only a little: 0005, with 2 baked credentials, still scores 7 and 8.
- `gemma4:31b` scores 1 on every bundle with host control, 11 of 20, reasoning that a read-write Docker socket "allows it to assume any identity on the host". `qwen3.8:27b` scores the same bundles 2–6.
- Whether host control is an identity failure or only a containment one is for the rubric to say, and the identity guide is silent.

**`qwen3.8:27b` is unstable at temperature 0.7.**
- Its 3 samples differ by 1.9 on average. On 0003 identity, for example, they were 7, 2 and 4.
- Across the two runs it repeated its median on 14 of 32 bundle-categories; `gemma4:31b` repeated on 25.

### Routing (distilabel run)

The gateway routed the 32 bundle-categories that were scored (the other 8 are `INSUFFICIENT_EVIDENCE`):
- **auto_accept:** 12 (identity 5, containment 7).
- **manual_review:** 20 (identity 15, containment 5).
  - The teachers' medians were more than a point apart on 15.
  - `qwen3.8:27b`'s samples spread by more than 2 on 10.
  - Some rows had both reasons.
- **auto_reject:** 0.
- **Anchor breaches:** none. No label broke the privileged + root anchor.

The review queue is `data/pilot2/distilabel/review.csv`, with blank columns for a human's score and note. It is the natural first batch for the hand-labelled holdout.

### Per bundle

Medians from pilot 1's `qwen3:14b`, then `qwen3.8:27b` and `gemma4:31b` from the distilabel run. The route is the gateway's decision: ✓ is auto_accept. Bold marks the facts a reviewer would expect to pull a score down.

| # | ctx | what the labeller could see | identity (14b / q3.8 / g4) | containment (14b / q3.8 / g4) |
|---|---|---|---|---|
| 0000 | C | non-root; permissions blind; no host mounts; no credentials | 9 / 7 / 10 review | — / — / — |
| 0001 | A | non-root; not privileged; no host mounts; no credentials; caps NET_BIND_SERVICE; root fs read-only | 9 / 7 / 8 review | 9 / 6 / 5 review |
| 0002 | C | gateway-fronted; root; permissions blind; mounts **host etc**, **host root**; gateway credential only | 7 / 3 / 1 review | — / — / — |
| 0003 | C | non-root; permissions blind; mounts **docker socket**; 4 credentials, **1 baked** | 9 / 4 / 1 review | — / — / — |
| 0004 | A | root; not privileged; mounts **docker socket**; 4 credentials, provenance blind; caps NET_BIND_SERVICE; root fs **writable** | 6 / 4 / 1 review | 2 / 1 / 1 ✓ |
| 0005 | D | non-root; not privileged; no mounts; 2 credentials, **2 baked**; caps **ALL**; root fs **writable** | 9 / 7 / 8 ✓ | 8 / 3 / 3 ✓ |
| 0006 | A | non-root; not privileged; no host mounts; no credentials; caps **ALL**; root fs **writable** | 9 / 7 / 8 review | 7 / 3 / 3 ✓ |
| 0007 | E | gateway-fronted; root; not privileged; mounts **host root**; gateway credential only; caps **ALL**; root fs read-only | 8 / 3 / 1 review | 6 / 5 / 1 review |
| 0008 | E | non-root; permissions blind; no host mounts; 4 credentials, **2 baked** | 9 / 6 / 5 review | — / — / — |
| 0009 | A | root; **privileged**; no mounts; 1 credential, provenance blind; caps NET_BIND_SERVICE; root fs **writable** | 6 / 4 / 1 review | 3 / 2 / 1 ✓ |
| 0010 | E | gateway-fronted; non-root; not privileged; no mounts; gateway credential only; caps **SYS_ADMIN**; root fs **writable** | 9 / 8 / 8 ✓ | 7 / 4 / 2 review |
| 0011 | D | non-root; not privileged; mounts **host root**; 4 credentials, none baked; caps none; root fs **writable** | 9 / 6 / 1 review | 7 / 2 / 1 review |
| 0012 | D | root; not privileged; no host mounts; 4 credentials, none baked; caps **SYS_ADMIN**; root fs read-only | 9 / 6 / 8 review | 8 / 5 / 3 review |
| 0013 | D | root; **privileged**; mounts **docker socket**, **host root**; 3 credentials, **2 baked**; caps **ALL**; root fs read-only | 6 / 2 / 1 ✓ | 1 / 1 / 1 ✓ |
| 0014 | A | root; permissions blind; mounts **host root**; 4 credentials, provenance blind | 6 / 3 / 1 review | — / — / — |
| 0015 | C | non-root; **privileged**; mounts **docker socket**; 3 credentials, **1 baked**; caps NET_BIND_SERVICE; root fs **writable** | 8 / 4 / 1 review | 1 / 1 / 1 ✓ |
| 0016 | A | non-root; permissions blind; mounts **docker socket**; 1 credential, provenance blind | 8 / 4 / 1 review | — / — / — |
| 0017 | C | non-root; not privileged; no host mounts; no credentials; caps NET_ADMIN, SYS_PTRACE; root fs read-only | 10 / 9 / 10 ✓ | 8 / 4 / 4 ✓ |
| 0018 | B | non-root; permissions blind; mounts blind; 3 credentials, none baked | 8 / 7 / 8 ✓ | — / — / — |
| 0019 | A | non-root; permissions blind; mounts **docker socket**, **host etc**; 4 credentials, provenance blind | 7 / 5 / 1 review | — / — / — |

### Next steps

1. **Decide whether host control is an identity failure.**
   - Write the answer into the `identity` guide, together with what "baked" means (input contract Part 5.5), then relabel identity.
   - This is now the largest source of disagreement: 15 of the 20 review rows are identity.
2. **Relabel with `qwen3.8:27b` at a lower temperature, such as 0.3,** and compare its spread. Its instability alone sends 10 rows to review.
3. **Label the 20 review rows by hand** (`review.csv`). They are the first part of the protected holdout.
4. **Teach `check.py` about capabilities.** `ALL`, `SYS_ADMIN` and a writable root filesystem should count, so that the containment check measures the graded middle.
5. **Reorder `run.py` to run one teacher at a time and port the gateway** (see the recommendation below). Then retire the distilabel driver.
6. **Re-time on Ollama 0.34.4 or later,** once `asp-model-bench` is not using the server.

## Distilabel: what it bought and what it cost

`datagen.distil_run` runs the same steps as `datagen.run` as a distilabel DAG, and adds the prototype's routing gateway. Its custom client and steps are in `datagen/distil.py`.

**Recommendation: do not adopt it for this pipeline.**
- Its measured gain, 18%, came from running one teacher at a time with each bundle's calls together. The plain loop would get that from a reorder.
- The routing gateway and the review queue are plain Python and port over as they are.
- Against that, it brings an unmaintained dependency, a client we had to write ourselves, and new ways to fail quietly.
- If generation moves to a GPU server, where concurrent calls pay, look at a maintained framework first (see below).

**State of the project (checked 2026-09-28):**
- **Releases:** the latest is 1.5.3, from 2025-01-28. Nothing has been released for 20 months.
- **Maintainers:** the README says the original authors have moved on, and community members are working towards 1.6.0 on `develop`. That branch is unreleased, and its last commit was on 2025-11-04.
- **Activity:** 81 open issues and 27 open PRs. Nothing has been merged to `main` since 2025-12-15.
- **Licence and Python:** Apache-2.0, Python 3.9–3.12.

**What it bought:**
- **The DAG as code.**
  - Two generators fan in to `assemble`, two labellers fan in to `combine`, and the gateway fans out to three outputs.
  - It is validated before any model is called. That caught one real bug: a step with two parents has to take `*inputs`.
- **Load groups.** One teacher is loaded at a time, in an order we choose. This made 3 model loads instead of the plain loop's 64, and it is where the 18% came from, together with rows arriving grouped by bundle.
- **Output:** each output branch becomes a Hugging Face dataset, with `push_to_hub` available.

**What it cost:**
- **Concurrency, its main performance feature, made this Mac slower.**
  - Four `gemma4:31b` calls in flight took a median 206 s each, against 5–50 s one at a time.
  - `qwen3.8:27b` cannot run in parallel at all on Ollama 0.33.3.
  - The trial runs one call at a time (`--parallel 1`).
- **Scheduling is on us.** distilabel sends a batch's calls as it likes. The first working version took turns per call, which interleaved bundles and made every label call a cold read: 49 s instead of 5 s (`data/pilot2/aborted-interleaved/`). The fix is in `OllamaChat`: a row keeps its turn for all of its samples.
- **Its own Ollama client does not do what the pilot needs, so `distil.OllamaChat` replaces it.**
  - `OllamaLLM` in 1.5.3 takes `format="json"` but not a JSON schema. The schema is what fixes list lengths, and `assemble` depends on them.
  - It cannot turn thinking off.
  - A failed call raises inside its own error handler (issue #1175, whose fix is unmerged).
  - `OpenAILLM` needs `instructor` for structured output. It asks for several samples with `n`, which Ollama ignores, and caps output at 128 tokens by default.
  - The prototype's `CANDIDATES_PER_INSTRUCTION` would therefore have produced one candidate, not three.
- **Stopping a run is not clean.**
  - Its process pool is not daemonic. `kill` on the driver leaves every step worker running and calling the model.
  - An hour after their runs were stopped, nine worker processes were still alive, and one was still labelling.
  - Only Ctrl-C shuts a run down properly.
- **Failures are quiet.**
  - An exception in a step nulls its whole batch, and the run carries on and "succeeds".
  - `OllamaChat` limits the damage by returning `None` for the one failed call.
- **Blindness is on us.**
  - Every upstream column rides along to every step, including the scenario the labeller must never see.
  - A column named `system_prompt` would be injected into the prompt.
  - `LabelBundle.format_input` reads the bundle and the category, and nothing else.
- **The plumbing has sharp edges.**
  - Rows are buffered in Arrow, where a nested value whose shape changes between batches can fail (issue #935). Values therefore move between steps as JSON strings.
  - Every step is its own spawned process, so custom steps must live in an importable module.
  - A `**kwargs` in a client's signature is read as a required runtime parameter.
- **There is no per-call timing.** Its statistics hold token counts only; `OllamaChat` logs its own.
- **Resume through its cache is not safe to rely on.** A resumed pipeline can hang (issue #1065). `distil_run` always starts fresh.
- **Code size.**
  - The plain driver, `run.py`, is 134 lines.
  - The distilabel driver is `distil_run.py` (177 lines) plus `distil.py` (306), on top of the same modules.
  - About 75 of those 306 lines are the gateway, which the plain driver does not have.

**Maintained alternatives** (status on 2026-09-28):
- **Bespoke `curator`:** Apache-2.0, active. Supports Ollama and OpenAI-compatible servers, with structured output, caching and retries.
- **NVIDIA NeMo Data Designer:** Apache-2.0, active. Has samplers, LLM columns, judges and resume.
- **Meta `synthetic-data-kit`** and **DataDreamer:** both stale.

## The distilabel prototype against the current rules

An older prototype (`aispm_pipeline_run.py`, `aispm_steps.py` and an implementation brief) built this pipeline on distilabel. It was written for the generation page as it stood before 2026-09-08. The page's banner and the design doc have since changed what the data is for. Where the two disagree, this repo follows the current rules:

| The prototype | The current rule | What the distilabel trial does |
|---|---|---|
| One teacher, `qwen2.5:32b`, for every step, including the judge. DeepSeek and Kimi K2 are named as alternatives, served by vLLM. | Two open-weight teachers from meaningfully different families, mixed (generation page §3 and §3.1, carried forward). | `qwen3.8:27b` (Alibaba) and `gemma4:31b` (Google), through Ollama. Kimi K2 and DeepSeek V-series do not fit 48 GB, and `deepseek-r1:32b` is a Qwen2.5 base, so pairing it with Qwen would not mix families. |
| Two outputs: unlabelled profiles for LightGBM classifiers, and (config → assessment) pairs for a report-writing SLM. | Neither model is being built. One corpus: bundle → score · reason per category (page banner; design doc §3). | One output: blind labels per bundle and category. |
| Taxonomy is OWASP ASI01–ASI10 plus data governance. | Our own eight categories; ASI is a published cross-reference (page banner; design doc). | `contract.CATEGORIES`. This run scores `identity` and `containment`. |
| Stage 1 asks the teacher for "an agent that has unrestricted/overprivileged tool access", and for "least-privilege best practices". | Never name the risk level at generation time (page §1; design doc). | Stage 1 dropped. Code samples the facts; the teacher writes only the surface, through `generate.guard`. |
| Free-text configs: system prompt, tool definitions, environment. | Evidence Bundle Schema v1, with blindness generated deliberately. | Bundles from `assemble.py`, validated. |
| A deterministic gate on planted vulnerabilities, an LLM judge of remediation, and keep-best-per-scenario. | §5 no longer applies. Mitigation targets come from the catalogue, never from a teacher (design doc). | The gateway is kept and re-aimed at labels ([Routing](#routing-distilabel-run)). No judge, no remediation text. No best-candidate pick: the target is every sample's distribution, and picking one would throw away the spread. |
| Classes `safe` / `moderate` / `critical`. | Integer 0–10, 10 safest. The band is derived afterwards from thresholds the model is not told (design doc §4). | 0–10. |
| Model and knobs by environment variable. | Not specified. | `DATAGEN_TEACHERS` overrides the pair for a quick run; volume is `--n`, `--k` and `--categories`. |

Not a contradiction, but still open: the page now puts harvesting real configurations first. Neither pipeline harvests yet.

## Results: pilot 1 (2026-09-24, MacBook Air)

**The pipeline works; the labels are not yet good enough to train on.**
- **Bundles:** all 20 are schema-valid, with realistic blindness.
- **Containment:** the larger teacher, `qwen3:14b`, is close to usable.
- **Identity:** every teacher tried gets it wrong. The clearest failure: they treat a credential baked into the image as safe.

### Setup

- **Batch:** 20 bundles, seed 20260924.
- **Contexts:** A×7, B×1, C×5, D×4, E×3. 3 bundles are gateway-fronted.
- **Categories:** `identity` and `containment`.
- **Labelling:** each teacher scored each category 3 times at temperature 0.7. The tables show the median.
- **Teachers:**
  - `qwen2.5:7b` and `mistral-nemo` labelled in the main run, as the two-teacher mix (`data/labels.jsonl`).
  - `qwen3:14b` relabelled the same bundles afterwards, so it compares on identical input (`data/labels.qwen3-14b.jsonl`).

**Coverage:**
- `identity` was evaluable on all 20.
- `containment` was `INSUFFICIENT_EVIDENCE` on 8 of 20. Seven of those are pack 14's blind `permissions`, and one is context B, where mounts are blind too.

### Do the labels follow the facts?

The check compares bundles where a fact is visible to the labeller with bundles where it isn't. A gap in the right direction shows a teacher reads the fact; it doesn't show the scores are right. Reproduce with `python -m datagen.check`.

| check | mistral-nemo | qwen2.5:7b | qwen3:14b |
|---|---|---|---|
| containment: host reach visible vs not (should be much lower) | 6.7 vs 8.0 | 3.0 vs 6.3 | **3.3 vs 7.8** |
| containment: privileged + root scored ≤ 2 (the rubric anchor is 1) | 0/2 | 2/2 | 1/2 |
| identity: a baked credential visible vs not (should be lower) | 7.4 vs 7.8 ✗ | 8.0 vs 5.9 ✗ | 8.2 vs 8.0 ✗ |
| identity: no credentials vs some (should be higher) | 8.0 vs 7.6 | 3.8 vs 7.1 ✗ | **9.2 vs 7.8** |
| spread across a teacher's own 3 samples | 1.53 | 1.53 | **0.47** |

Host reach means privileged, a Docker socket mount, or the host's `/` mounted.

How often two teachers' medians land within 1 point of each other:

| pair | identity | containment |
|---|---|---|
| qwen2.5:7b ~ mistral-nemo | 15/20 | 2/12 |
| qwen2.5:7b ~ qwen3:14b | 12/20 | 7/12 |
| mistral-nemo ~ qwen3:14b | 14/20 | 7/12 |

### Per bundle

The middle column is what the bundle showed the labeller, built from the scenario but only where the carrying attribute was `ANSWERED` or `PARTIAL`. Bold marks the facts a reviewer would expect to pull a score down. A dash means `INSUFFICIENT_EVIDENCE`, so the teacher was not asked.

| # | ctx | what the labeller could see | identity (7b / nemo / 14b) | containment (7b / nemo / 14b) |
|---|---|---|---|---|
| 0000 | C | non-root; permissions blind; no host mounts; no credentials | 8 / 9 / 9 | — / — / — |
| 0001 | A | non-root; not privileged; no host mounts; no credentials | 2 / 9 / 9 | 7 / 9 / 9 |
| 0002 | C | gateway-fronted; root; permissions blind; mounts **host etc**, **host root**; gateway credential only | 8 / 7 / 7 | — / — / — |
| 0003 | C | non-root; permissions blind; mounts **docker socket**; 4 credentials, **1 baked** | 8 / 7 / 9 | — / — / — |
| 0004 | A | root; not privileged; mounts **docker socket**; 4 credentials, provenance blind | 8 / 8 / 6 | 3 / 6 / 2 |
| 0005 | D | non-root; not privileged; no mounts; 2 credentials, **2 baked** | 8 / 8 / 9 | 7 / 8 / 8 |
| 0006 | A | non-root; not privileged; no host mounts; no credentials | 2 / 7 / 9 | 6 / 7 / 7 |
| 0007 | E | gateway-fronted; root; not privileged; mounts **host root**; gateway credential only | 8 / 8 / 8 | 6 / 8 / 6 |
| 0008 | E | non-root; permissions blind; no host mounts; 4 credentials, **2 baked** | 8 / 7 / 9 | — / — / — |
| 0009 | A | root; **privileged**; no mounts; 1 credential, provenance blind | 2 / 7 / 6 | 0 / 6 / 3 |
| 0010 | E | gateway-fronted; non-root; not privileged; no mounts; gateway credential only | 8 / 8 / 9 | 6 / 8 / 7 |
| 0011 | D | non-root; not privileged; mounts **host root**; 4 credentials, none baked | 8 / 7 / 9 | 6 / 8 / 7 |
| 0012 | D | root; not privileged; no host mounts; 4 credentials, none baked | 8 / 9 / 9 | 6 / 8 / 8 |
| 0013 | D | root; **privileged**; mounts **docker socket**, **host root**; 3 credentials, **2 baked** | 8 / 7 / 6 | 0 / 5 / 1 |
| 0014 | A | root; permissions blind; mounts **host root**; 4 credentials, provenance blind | 2 / 7 / 6 | — / — / — |
| 0015 | C | non-root; **privileged**; mounts **docker socket**; 3 credentials, **1 baked** | 8 / 8 / 8 | 3 / 7 / 1 |
| 0016 | A | non-root; permissions blind; mounts **docker socket**; 1 credential, provenance blind | 6 / 7 / 8 | — / — / — |
| 0017 | C | non-root; not privileged; no host mounts; no credentials | 3 / 7 / 10 | 6 / 8 / 8 |
| 0018 | B | non-root; permissions blind; mounts blind; 3 credentials, none baked | 9 / 9 / 8 | — / — / — |
| 0019 | A | non-root; permissions blind; mounts **docker socket**, **host etc**; 4 credentials, provenance blind | 7 / 8 / 7 | — / — / — |

### What went wrong, by teacher and category

**Containment:**
- **qwen3:14b is close to usable.**
  - It scored 1 on the two worst bundles: 0013 (privileged, root, Docker socket and host `/`) and 0015 (privileged, Docker socket).
  - It scored 7–9 on bundles with no host reach.
  - Its three samples rarely differ.
  - Its miss is 0009: privileged and root with no mounts, which it scored 3 against an anchor of 1. Host `/` mounted read-write is arguably scored too leniently: 6 as root (0007) and 7 as non-root (0011).
- **qwen2.5:7b** points the right way but scatters. It also cited "privileged mode" on 0011, which is not privileged.
- **mistral-nemo** compresses everything into 5–9, including 5 for 0013.

**Identity:**
- **No teacher reads a baked credential as a problem.** On 0008, qwen3:14b wrote that the credentials are "baked i[nto the image] … securely managed". The input contract (Part 5.5) says the opposite: a baked credential is readable by anyone who can pull the image and is unrotatable in practice. It is also the condition of the `baked_secret` hard cap.
- **qwen2.5:7b** scores every agent holding no credentials 2–3 (0001, 0006, 0017): its reasons treat an `ABSENT` credential inventory as dangerous.
- **Medians cluster at 7–9.** The facts are balanced; the labels are not.

**Across both categories:**
- **The generator's surface text is weak in places:** a model named `bard-llm-v1`, and destinations that are not hostnames (`hr-interview-scheduling`).

### Hardware

- **Machine:** a MacBook Air, M3, 16 GB. macOS gives the GPU roughly 10–12 GB of that.
- **Ceiling:** about 14B parameters at 4-bit. `qwen3:14b` loads at 10 GB, entirely on the GPU.
- **Speed:** about 56 s for the first call on a bundle, then about 6 s per call once the bundle is cached. That comes to about 90 s per bundle for 2 categories × 3 samples.
- **What that allows:** fine for pilots. A corpus of thousands of bundles would take days on a fanless laptop that throttles.
- **What doesn't fit:** the larger teachers the generation page names (big Qwen, DeepSeek, Kimi K2) need a GPU machine.

### Next steps, as of pilot 1

Where they stand after pilot 2: 1 and 3 are still open. 2 is done: `gemma4:31b` is the second family. 4 is done in the distilabel driver's gateway, which sends anchor breaches to review rather than rejecting them.

1. **Fix identity's vocabulary:** add what "baked" means (input contract Part 5.5) to the `identity` guide, then relabel identity with `qwen3:14b`. About 10 minutes.
2. **Replace mistral-nemo as the second teacher.** The mix needs a different model family of similar strength; `phi4` (14B, MIT) fits the laptop.
3. **Label 20 bundles by hand** and measure each teacher against them before scaling. The generation page's human seed set and protected holdout are still the only signal that is not circular.
4. **Add a consistency gate:** reject a label that contradicts a visible fact the rubric anchors, for example privileged + root must score ≤ 2 on containment. This is generation page §5's deterministic gate, repurposed.

## Assumptions and departures, to review

- **Rule pack 15 is invented.** Pack 14 has no `permissions` collector, and `containment` requires `permissions`, so under pack 14 containment is never evaluable. Two thirds of scenarios therefore assume a pack 15 that collects `permissions`. No such pack exists yet.
- **Context weights (A .25, B .10, C .25, D .30, E .10) are a guess.** The input contract lists the real mix as unmeasured (Part 9).
- **Category guides:** labellers get a one-paragraph definition for `identity` and `containment` (`contract.CATEGORY_GUIDE`). The 7B teachers misread the one-line question: they took `identity` to mean "which harness". Production sends only the question.
- **No harvest yet.** The updated generation page puts harvesting real configurations first, with generation filling the gaps. This pilot only generates.
- **No human pass yet.** No human has edited drafts or labelled a held-out set. Treat every label here as an unreviewed teacher label.
- **Mitigations are not generated.** The design doc says mitigation targets come from the catalogue, not from a teacher.
- **Teachers sized for the machine:** pilot 1 used 7B–14B models, which is what fits a 16 GB Mac. Pilot 2 uses about 30B at 4-bit, which is what fits 48 GB. Larger teachers (`qwen3.5:122b`, `gpt-oss:120b`, Kimi, the DeepSeek V-series) need a bigger machine.
- **Superseded parts of the generation page are skipped:** the planted-vulnerability gates and the LLM judge (§5) were built for the report writer, which the design no longer has.

## Run

```bash
ollama serve &                       # pilot 2: qwen3.8:27b, gemma4:31b. Pilot 1: qwen2.5:7b, mistral-nemo, qwen3:14b
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m datagen.run --n 20 --out data/pilot2/plain               # plain driver: generate + label with the two-teacher mix
.venv/bin/python -m datagen.relabel --teacher qwen3:14b                     # label pilot 1's bundles with another teacher
.venv/bin/python -m datagen.check --data data/pilot2/plain                  # do the labels follow the facts?

.venv/bin/pip install -r requirements-distilabel.txt
.venv/bin/python -m datagen.distil_run --n 20 --out data/pilot2/distilabel   # distilabel driver, with the gateway
DATAGEN_TEACHERS=qwen2.5:7b,mistral-nemo .venv/bin/python -m datagen.distil_run --n 3 --k 2 --out /tmp/smoke   # quick check on small models
```

**Resuming.**
- A rerun of `run` with the same `--seed` and `--out` resumes where it stopped, and so does `relabel`.
- `distil_run` always starts fresh, and it refuses an `--out` that already holds a run.

**Stopping `distil_run`.**
- Stop it with Ctrl-C.
- Do not use `kill`: its step workers survive and keep calling the model.

**Timing.**
- Both drivers write `calls.jsonl` (one line per model call) and `timing.md`.
- Keep other Ollama clients off the server while timing a run.
- `OLLAMA_NUM_PARALLEL` above 1 slows this machine down (see Timing).

**Speed.**
- On the M3 with 16 GB, `run` took about 2–4 minutes per bundle: one generation call plus 3 samples × 2 teachers × 2 categories.
- On the Mac mini with pilot 2's teachers it takes about 5 minutes.

## Output (`data/`)

Pilot 1's files are at the top of `data/`; pilot 2's are under `data/pilot2/`.

| File | What |
|---|---|
| `bundles/*.json` | The generated evidence bundles. |
| `scenarios.jsonl` | Per bundle: the sampled facts, the teacher's surface, which teacher generated it, and any schema problems. Keep it away from labellers. |
| `labels.jsonl` | Main-run labels from `qwen2.5:7b` and `mistral-nemo`. Per bundle × category × teacher: every sample (score + reason), a distribution over 0-10 (the soft target), the median, or `INSUFFICIENT_EVIDENCE` / `FAILED`. |
| `labels.qwen3-14b.jsonl` | The same, from `qwen3:14b` on the same bundles. |
| `summary.md` | Generated by `run`: validity, coverage, agreement and histograms for the main-run teachers. |
| `pilot2/plain/`, `pilot2/distilabel/` | Pilot 2, run through each driver: the same files as above, plus `calls.jsonl`, `timing.json` and `timing.md`. |
| `pilot2/distilabel/routed.jsonl` | Per bundle × category: the gateway's status, why, and the pooled training target (a median and a distribution over 0-10 from both teachers' samples). |
| `pilot2/distilabel/review.csv` | The `manual_review` rows, with blank `human_score` and `human_note` columns. |
| `pilot2/aborted-parallel4/`, `pilot2/aborted-interleaved/` | Call logs of two stopped distilabel runs, kept as evidence: 4 calls in flight, and per-call turns that interleaved bundles. |
