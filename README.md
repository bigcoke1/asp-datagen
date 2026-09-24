# asp-datagen

Synthetic training data for agent security profiling. The pipeline generates evidence bundles and has open-weight teachers label them per risk category. The labelled pairs are what a fine-tuned scorer such as [Laya](https://huggingface.co/convaiinnovations/laya) trains on.

It follows the **Synthetic Training Data Generation Pipeline** page (Confluence `AgBAAg`) for method. Where that page is stale, the design doc in `railxia/docs` (`design/2026-09-03-agent-profiling`) wins.

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
```

## Rules it follows, and where each comes from

| Rule | Source | How |
|---|---|---|
| Never name the risk level when generating | Generation page §1 | Code samples facts evenly across their values. The teacher is told only the domain, job, harness and counts, and `generate.guard` refuses any prompt that contains a risk word. |
| Class balance | Generation page §7 | Balance comes from how facts are sampled, not from labels. It does not survive labelling yet (see Results). |
| Open-weight teachers, two of them, mixed | Generation page §3, design doc | `qwen2.5:7b` and `mistral-nemo`, both Apache-2.0, served locally by Ollama. Generation mixes them 70/30. Both label every bundle. `qwen3:14b` was tried as a larger labeller. |
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
| Surface: agent name, workdir, data directory, model name, tool names, credential variable names, hostnames, skill names and descriptions, MCP server names, deployment and namespace | An open-weight teacher, per bundle (`generate.py`): 15 by `qwen2.5:7b`, 5 by `mistral-nemo` |
| Every label (score, reason, distribution) | Open-weight teachers only (`label.py`) |

## Results (pilot, 2026-09-24)

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

### Next steps

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
- **Laptop-sized teachers:** 7B-14B models, which is what fits a 16 GB Mac (see Hardware).
- **Superseded parts of the generation page are skipped:** the planted-vulnerability gates and the LLM judge (§5) were built for the report writer, which the design no longer has.

## Run

```bash
ollama serve &                       # models: qwen2.5:7b, mistral-nemo, qwen3:14b
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m datagen.run --n 20 --categories identity containment   # generate + label with the two-teacher mix
.venv/bin/python -m datagen.relabel --teacher qwen3:14b                    # label the same bundles with another teacher
.venv/bin/python -m datagen.check                                          # do the labels follow the facts?
```

A rerun with the same `--seed` and `--out` resumes where it stopped, as does `relabel`. `run` takes about 2–4 minutes per bundle on an M3 with 16 GB: one generation call plus 3 samples × 2 teachers × 2 categories.

## Output (`data/`)

| File | What |
|---|---|
| `bundles/*.json` | The generated evidence bundles. |
| `scenarios.jsonl` | Per bundle: the sampled facts, the teacher's surface, which teacher generated it, and any schema problems. Keep it away from labellers. |
| `labels.jsonl` | Main-run labels from `qwen2.5:7b` and `mistral-nemo`. Per bundle × category × teacher: every sample (score + reason), a distribution over 0-10 (the soft target), the median, or `INSUFFICIENT_EVIDENCE` / `FAILED`. |
| `labels.qwen3-14b.jsonl` | The same, from `qwen3:14b` on the same bundles. |
| `summary.md` | Generated by `run`: validity, coverage, agreement and histograms for the main-run teachers. |
