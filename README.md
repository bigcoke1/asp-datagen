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
label.py       two teachers, k samples each       sees only the bundle; 0-10, 10 safest; coverage-gated
```

## Rules it follows, and where each comes from

| Rule | Source | How |
|---|---|---|
| Never name the risk level when generating | Generation page §1 | Code samples facts evenly across their values. The teacher is told only the domain, job, harness and counts, and `generate.guard` refuses any prompt that contains a risk word. |
| Class balance | Generation page §7 | Balance comes from how facts are sampled, not from labels. Check the histograms in `data/summary.md`. |
| Open-weight teachers, two of them, mixed | Generation page §3, design doc | `qwen2.5:7b` and `mistral-nemo`, both Apache-2.0, served locally by Ollama. Generation mixes them 70/30. Both label every bundle. |
| Generate blindness, not just configuration | Generation page (update), design doc | Each attribute's status follows the input contract's matrix for contexts A-E, plus the gateway-fronted modifier and the rule pack's gaps. |
| Closed enums only | Evidence Bundle Schema page | Every bundle is validated against `schema/evidence-bundle.schema.json`, which is the page's schema as copied into Rail Center's test vectors. |
| Blind labelling | Generation page §1 | The labeller sees the bundle and nothing else. The scenario is kept in `data/scenarios.jsonl` for audit. |
| A category with blind required inputs is not scored | Design doc §4 (coverage profiler) | These get `INSUFFICIENT_EVIDENCE`, and the teacher is not asked. |
| 0-10 scale, 10 safest | Design doc | The rubric is the prototype's `STATES` + `SCALE_V2`. |

## Assumptions and departures, to review

- **Rule pack 15 is invented.** Pack 14 has no `permissions` collector, and `containment` requires `permissions`, so under pack 14 containment is never evaluable. Two thirds of scenarios therefore assume a pack 15 that collects `permissions`. No such pack exists yet.
- **Context weights (A .25, B .10, C .25, D .30, E .10) are a guess.** The input contract lists the real mix as unmeasured (Part 9).
- **Category guides:** labellers get a one-paragraph definition for `identity` and `containment` (`contract.CATEGORY_GUIDE`). The 7B teachers misread the one-line question: they took `identity` to mean "which harness". Production sends only the question.
- **No harvest yet.** The updated generation page puts harvesting real configurations first, with generation filling the gaps. This pilot only generates.
- **No human pass yet.** No human has edited drafts or labelled a held-out set. Treat every label here as an unreviewed teacher label.
- **Mitigations are not generated.** The design doc says mitigation targets come from the catalogue, not from a teacher.
- **Small teachers:** 7B-12B models are what fit a 16 GB laptop. The generation page expects larger open-weight models on a GPU. Label quality is bounded by that.
- **Superseded parts of the generation page are skipped:** the planted-vulnerability gates and the LLM judge (§5) were built for the report writer, which the design no longer has.

## Run

```bash
ollama serve &                       # models: qwen2.5:7b, mistral-nemo
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m datagen.run --n 20 --categories identity containment
```

A rerun with the same `--seed` and `--out` resumes where it stopped. Each bundle takes about 2 minutes on an M3 with 16 GB: one generation call plus 3 samples × 2 teachers × 2 categories.

## Output (`data/`)

| File | What |
|---|---|
| `bundles/*.json` | The generated evidence bundles. |
| `scenarios.jsonl` | Per bundle: the sampled facts, the teacher's surface, which teacher generated it, and any schema problems. Keep it away from labellers. |
| `labels.jsonl` | Per bundle × category × teacher: every sample (score + reason), a distribution over 0-10 (the soft target), the median, or `INSUFFICIENT_EVIDENCE` / `FAILED`. |
| `summary.md` | Validity, coverage, teacher agreement, score histograms, and a per-bundle table with the facts next to the labels. |
