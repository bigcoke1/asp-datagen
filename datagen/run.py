"""Generate, validate and label a batch of evidence bundles.

    python -m datagen.run --n 20 --categories identity containment

Writes data/scenarios.jsonl (the facts, for audit only), data/bundles/*.json, data/labels.jsonl
and data/summary.md. Rerunning with the same --seed and --out resumes: a bundle already written is
not regenerated, and a label already written is not asked again.
"""
import argparse
import json
import random
import statistics
import time
from collections import Counter
from pathlib import Path

from datagen import assemble, generate, label, scenarios, validate
from datagen.contract import CATEGORIES
from datagen.llm import TEACHERS

GEN_MIX = {"qwen2.5:7b": 0.7, "mistral-nemo": 0.3}  # generation page §3.1: mix in a different teacher


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20260924)
    ap.add_argument("--categories", nargs="+", default=["identity", "containment"], choices=list(CATEGORIES))
    ap.add_argument("--k", type=int, default=3, help="samples per teacher per category")
    ap.add_argument("--out", default="data")
    args = ap.parse_args()

    out = Path(args.out)
    (out / "bundles").mkdir(parents=True, exist_ok=True)
    scen_path, label_path = out / "scenarios.jsonl", out / "labels.jsonl"
    done_scen = {r["idx"]: r for r in read_jsonl(scen_path)}
    done_labels = {(r["bundle_id"], r["category"], r["teacher"]) for r in read_jsonl(label_path)}

    for idx in range(args.n):
        rng = random.Random(args.seed * 1000 + idx)
        t0 = time.time()
        if idx in done_scen:
            rec = done_scen[idx]
            b = json.loads((out / "bundles" / f"{rec['bundle_id']}.json").read_text())
        else:
            s = scenarios.sample(rng)
            teacher = rng.choices(list(GEN_MIX), weights=list(GEN_MIX.values()))[0]
            surf = generate.surface(s, teacher, seed=args.seed + idx)
            b = assemble.bundle(s, surf, idx, rng)
            errs = validate.problems(b)
            rec = {"idx": idx, "bundle_id": b["bundle_id"], "generator": teacher, "scenario": s, "surface": surf,
                   "schema_problems": errs}
            (out / "bundles" / f"{b['bundle_id']}.json").write_text(json.dumps(b, indent=2, ensure_ascii=False))
            with scen_path.open("a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            done_scen[idx] = rec
        if rec["schema_problems"]:
            print(f"[{idx:02d}] {b['bundle_id']} INVALID, not labelled: {rec['schema_problems'][:3]}")
            continue
        for cat in args.categories:
            for teacher in TEACHERS:
                if (b["bundle_id"], cat, teacher) in done_labels:
                    continue
                res = label.label(b, cat, teacher, args.k, seed=args.seed + idx * 100)
                with label_path.open("a") as f:
                    f.write(json.dumps({"bundle_id": b["bundle_id"], "category": cat, "teacher": teacher, **res},
                                       ensure_ascii=False) + "\n")
        print(f"[{idx:02d}] {b['bundle_id']} ctx {b['inputs_attempted'] and rec['scenario']['context']} "
              f"({time.time() - t0:.0f}s)", flush=True)

    summarize(out, args.categories)


def summarize(out: Path, categories: list[str]) -> None:
    scen = {r["bundle_id"]: r for r in read_jsonl(out / "scenarios.jsonl")}
    labels = read_jsonl(out / "labels.jsonl")
    by = {(l["bundle_id"], l["category"], l["teacher"]): l for l in labels}
    teachers = list(TEACHERS)
    lines = ["# Pilot batch summary", "",
             f"{len(scen)} bundles generated, {sum(not r['schema_problems'] for r in scen.values())} valid against the "
             f"Evidence Bundle Schema. Generators: {dict(Counter(r['generator'] for r in scen.values()))}.", ""]

    for cat in categories:
        rows = [(bid, [by.get((bid, cat, t)) for t in teachers]) for bid in scen]
        scored = [(bid, ls) for bid, ls in rows if all(l and l["outcome"] == "SCORED" for l in ls)]
        insufficient = sum(1 for _, ls in rows if ls[0] and ls[0]["outcome"] == "INSUFFICIENT_EVIDENCE")
        lines += [f"## {cat}", "",
                  f"Scored by both teachers: {len(scored)}. INSUFFICIENT_EVIDENCE: {insufficient}. "
                  f"Failed: {sum(1 for _, ls in rows if any(l and l['outcome'] == 'FAILED' for l in ls))}.", ""]
        if scored:
            diffs = [abs(ls[0]["median"] - ls[1]["median"]) for _, ls in scored]
            spread = [max(x["score"] for x in l["samples"] if x["valid"]) - min(x["score"] for x in l["samples"] if x["valid"])
                      for _, ls in scored for l in ls]
            lines += [f"- Teacher agreement: mean |median difference| {statistics.mean(diffs):.2f}; "
                      f"exact agreement on {sum(d == 0 for d in diffs)}/{len(diffs)}; within 1 on {sum(d <= 1 for d in diffs)}/{len(diffs)}.",
                      f"- Within-teacher spread across samples (max - min): mean {statistics.mean(spread):.2f}.",
                      "- Median score histogram (both teachers pooled): "
                      + " ".join(f"{v}:{c}" for v, c in sorted(Counter(l['median'] for _, ls in scored for l in ls).items())), ""]
        lines += ["| bundle | ctx | gw | user | privileged | mounts | creds (class/prov) | " + " | ".join(teachers) + " |",
                  "|---|---|---|---|---|---|---|" + "---|" * len(teachers)]
        for bid, ls in rows:
            s = scen[bid]["scenario"]
            cells = []
            for l in ls:
                if not l:
                    cells.append("-")
                elif l["outcome"] == "SCORED":
                    cells.append(f"{l['median']} ({','.join(str(x['score']) for x in l['samples'])})")
                elif l["outcome"] == "INSUFFICIENT_EVIDENCE":
                    cells.append("INSUFF (" + ", ".join(l["missing"]) + ")")
                else:
                    cells.append("FAILED")
            creds = ", ".join(f"{c['class'].replace('secret_', '')}/{c['provenance']}" for c in s["credentials"]) or "none"
            lines.append(f"| {bid} | {s['context']} | {'y' if s['gateway_fronted'] else ''} | {s['run_as']} | "
                         f"{'y' if s['privileged'] else ''} | {', '.join(s['mounts']) or 'none'} | {creds} | " + " | ".join(cells) + " |")
        lines.append("")
    lines += ["The scenario columns are the generator's facts, shown here for review only; the labellers never saw them. "
              "Where a bundle hid a fact (a BLIND or PARTIAL attribute), the labeller could not see it either.", ""]
    (out / "summary.md").write_text("\n".join(lines))
    print(f"wrote {out / 'summary.md'}")


if __name__ == "__main__":
    main()
