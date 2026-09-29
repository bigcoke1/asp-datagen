"""Generate, validate, label and route a batch of evidence bundles as a distilabel pipeline.

    python -m datagen.distil_run --n 20 --out data/pilot2/distilabel

The same method as `datagen.run`, run as a declared DAG, plus the prototype's three-way gateway.
Writes the same files as `datagen.run` (bundles/, scenarios.jsonl, labels.jsonl, summary.md), so
`datagen.check` reads either, and adds:
- routed.jsonl: per bundle x category, the gateway's status, why, and the pooled training target
- review.csv: the manual_review rows, with blank columns for a human's score and note
- calls.jsonl, timing.json and timing.md: where the time went

    scenarios_0 ─► surface_0 ─┐                     the first teacher writes 70% of surfaces, the second 30%
    scenarios_1 ─► surface_1 ─┴─► assemble ─┬─► valid ─► expand ─┬─► evaluable ─┬─► label_0 ─┐
                                            └─► invalid          └─► insufficient └─► label_1 ─┴─► combine ─► route
                                                                                            route ─┬─► auto_accept
                                                                                                   ├─► manual_review
                                                                                                   └─► auto_reject

Load groups run one teacher at a time: the two teachers do not fit in GPU memory together, and
without the groups Ollama would swap them in and out as the steps' calls interleave.
Always a fresh run (use_cache=False) so the timing covers the whole job; there is no resume.
"""
import argparse
import csv
import json
import time
from pathlib import Path

from distilabel.pipeline import Pipeline
from distilabel.steps import CombineOutputs, LoadDataFromDicts

from datagen import generate, timing
from datagen.contract import CATEGORIES
from datagen.distil import (AssembleBundle, ExpandCategories, KeepWhere, LabelBundle, OllamaChat, RouteLabel,
                            WriteSurface, plan)
from datagen.llm import GEN_MIX, SLOTS, TEACHERS
from datagen.run import summarize

STATUSES = ("auto_accept", "manual_review", "auto_reject")


def build(args, call_log: str) -> tuple[Pipeline, list[list[str]]]:
    teachers = list(TEACHERS)
    rows: dict[str, list[dict]] = {t: [] for t in GEN_MIX}
    for idx in range(args.n):
        _, s, gen = plan(args.seed, idx)
        rows[gen].append({"idx": idx, "generator": gen, "scenario_json": json.dumps(s),
                          "surface_prompt": generate.prompt(s), "surface_schema": json.dumps(generate._schema(s))})
    llm = lambda model, stage, temperature: OllamaChat(  # noqa: E731
        model=model, stage=stage, temperature=temperature, call_log=call_log,
        max_concurrency=min(args.parallel, SLOTS.get(model, args.parallel)))

    with Pipeline(name="asp-datagen") as pipeline:
        assemble = AssembleBundle(name="assemble", seed=args.seed)
        gen_steps = []
        for i, gen in enumerate(GEN_MIX):
            if rows[gen]:
                load = LoadDataFromDicts(name=f"scenarios_{i}", data=rows[gen], batch_size=args.batch)
                write = WriteSurface(name=f"surface_{i}", llm=llm(gen, "surface", 0.9), input_batch_size=args.batch,
                                     add_raw_input=False)
                load >> write >> assemble
                gen_steps.append((gen, load.name, write.name))
        valid = KeepWhere(name="valid", column="schema_problems", value="[]")
        invalid = KeepWhere(name="invalid", column="schema_problems", value="[]", negate=True)
        expand = ExpandCategories(name="expand", categories=args.categories)
        evaluable = KeepWhere(name="evaluable", column="missing", value="")
        insufficient = KeepWhere(name="insufficient", column="missing", value="", negate=True)
        labellers = [LabelBundle(name=f"label_{i}", llm=llm(t, "label", 0.7), num_generations=args.k,
                                 group_generations=True, input_batch_size=args.batch, add_raw_input=False,
                                 output_mappings={"score": f"scores_{i}", "reason": f"reasons_{i}", "model_name": f"teacher_{i}"})
                     for i, t in enumerate(teachers)]
        combine = CombineOutputs(name="combine")
        route = RouteLabel(name="route", teachers=teachers)
        leaves = [KeepWhere(name=st, column="status", value=st) for st in STATUSES]

        assemble >> [valid, invalid]
        valid >> expand >> [evaluable, insufficient]
        evaluable >> labellers >> combine >> route >> leaves

    # One teacher loaded at a time. The first generator writes; the second writes and then labels,
    # while it is still loaded; the first labels last. Two model loads per teacher at most.
    first = teachers.index(gen_steps[0][0])
    second = 1 - first
    groups = [[gen_steps[0][1], gen_steps[0][2]] + ([g[1] for g in gen_steps[1:]])]
    groups += [[g[2] for g in gen_steps[1:]]] if len(gen_steps) > 1 else []
    groups += [["assemble", "valid", "invalid", "expand", "evaluable", "insufficient", f"label_{second}"],
               [f"label_{first}", "combine", "route", *STATUSES]]
    return pipeline, groups


def rows_of(distiset, name: str) -> list[dict]:
    return distiset[name]["train"].to_list() if name in distiset else []


def write_outputs(distiset, out: Path) -> dict:
    teachers = list(TEACHERS)
    (out / "bundles").mkdir(parents=True, exist_ok=True)
    every = rows_of(distiset, "invalid") + rows_of(distiset, "insufficient") + [r for st in STATUSES for r in rows_of(distiset, st)]
    firsts: dict[int, dict] = {}
    for r in every:
        firsts.setdefault(r["idx"], r)
    with (out / "scenarios.jsonl").open("w") as f:
        for idx, r in sorted(firsts.items()):
            if r["bundle_json"]:
                (out / "bundles" / f"{r['bundle_id']}.json").write_text(json.dumps(json.loads(r["bundle_json"]), indent=2, ensure_ascii=False))
            f.write(json.dumps({"idx": idx, "bundle_id": r["bundle_id"], "generator": r["generator"],
                                "scenario": json.loads(r["scenario_json"]),
                                "surface": json.loads(r["surface_json"]) if r["surface_json"] else None,
                                "schema_problems": json.loads(r["schema_problems"])}, ensure_ascii=False) + "\n")

    routed = sorted((r for st in STATUSES for r in rows_of(distiset, st)), key=lambda r: (r["idx"], r["category"]))
    insufficient = sorted(rows_of(distiset, "insufficient"), key=lambda r: (r["idx"], r["category"]))
    with (out / "labels.jsonl").open("w") as f:
        for r in insufficient:
            for t in teachers:
                f.write(json.dumps({"bundle_id": r["bundle_id"], "category": r["category"], "teacher": t,
                                    "outcome": "INSUFFICIENT_EVIDENCE", "missing": r["missing"].split(",")}) + "\n")
        for r in routed:
            for t, lab in json.loads(r["labels_json"]).items():
                f.write(json.dumps({"bundle_id": r["bundle_id"], "category": r["category"], "teacher": t, **lab},
                                   ensure_ascii=False) + "\n")
    with (out / "routed.jsonl").open("w") as f:
        for r in routed:
            labs = json.loads(r["labels_json"])
            f.write(json.dumps({"bundle_id": r["bundle_id"], "category": r["category"], "status": r["status"],
                                "why": r["route_reason"], "medians": {t: l.get("median") for t, l in labs.items()},
                                "target": json.loads(r["target_json"])}, ensure_ascii=False) + "\n")
    with (out / "review.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["bundle_id", "category", "bundle_file", "why"]
                   + [c for t in teachers for c in (f"{t} median", f"{t} samples", f"{t} first reason")]
                   + ["human_score", "human_note"])
        for r in (r for r in routed if r["status"] == "manual_review"):
            labs = json.loads(r["labels_json"])
            w.writerow([r["bundle_id"], r["category"], f"bundles/{r['bundle_id']}.json", r["route_reason"]]
                       + [c for t in teachers for c in (labs[t].get("median"), " ".join(str(x["score"]) for x in labs[t]["samples"]),
                                                          next((x["reason"] for x in labs[t]["samples"] if x["valid"]), ""))]
                       + ["", ""])
    counts = {st: sum(r["status"] == st for r in routed) for st in STATUSES}
    counts |= {"insufficient_evidence": len(insufficient), "invalid_bundles": len(rows_of(distiset, "invalid"))}
    return counts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20260924)
    ap.add_argument("--categories", nargs="+", default=["identity", "containment"], choices=list(CATEGORIES))
    ap.add_argument("--k", type=int, default=3, help="samples per teacher per category")
    # 1 on a Mac: with 4 in flight, gemma4:31b label calls took 206 s each instead of 6-59 s, because
    # the slots lose each other's cached bundle and one slot's prefill stalls the others' decoding
    # (data/pilot2/aborted-parallel4). Raise it only on a server whose throughput grows with batching.
    ap.add_argument("--parallel", type=int, default=1, help="calls in flight per step; llm.SLOTS caps it per model")
    ap.add_argument("--batch", type=int, default=50, help="rows per distilabel batch")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    call_log = out / "calls.jsonl"
    if call_log.exists():
        raise SystemExit(f"{out} already holds a run; use a fresh --out")
    pipeline, groups = build(args, str(call_log.resolve()))
    started = time.time()
    distiset = pipeline.run(use_cache=False, load_groups=groups)
    wall = time.time() - started

    counts = write_outputs(distiset, out)
    summarize(out, args.categories)
    t = timing.summarise(out, wall, args.n, {
        "pipeline": "distilabel (datagen.distil_run)", "machine": timing.machine(list(TEACHERS)), "routing": counts,
        "settings": f"{len(args.categories)} categories, k={args.k} samples x {len(TEACHERS)} teachers, "
                    f"{args.parallel} calls in flight, batches of {args.batch}"})
    print(json.dumps(counts), f"\n{t['bundles']} bundles in {t['wall_s']:.0f} s; wrote {out}")


if __name__ == "__main__":
    main()
