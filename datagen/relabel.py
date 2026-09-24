"""Label bundles already generated with another teacher, so teachers compare on identical input.

    python -m datagen.relabel --teacher qwen3:14b

Writes data/labels.<teacher>.jsonl beside data/labels.jsonl and resumes the same way run.py does.
"""
import argparse
import json
import time
from pathlib import Path

from datagen import label
from datagen.run import read_jsonl


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--teacher", required=True)
    ap.add_argument("--data", default="data")
    ap.add_argument("--seed", type=int, default=20260924)
    ap.add_argument("--categories", nargs="+", default=["identity", "containment"])
    ap.add_argument("--k", type=int, default=3)
    args = ap.parse_args()

    data = Path(args.data)
    path = data / f"labels.{args.teacher.replace(':', '-')}.jsonl"
    done = {(r["bundle_id"], r["category"]) for r in read_jsonl(path)}
    for rec in read_jsonl(data / "scenarios.jsonl"):
        if rec["schema_problems"]:
            continue
        b = json.loads((data / "bundles" / f"{rec['bundle_id']}.json").read_text())
        t0 = time.time()
        for cat in args.categories:
            if (b["bundle_id"], cat) in done:
                continue
            res = label.label(b, cat, args.teacher, args.k, seed=args.seed + rec["idx"] * 100)
            with path.open("a") as f:
                f.write(json.dumps({"bundle_id": b["bundle_id"], "category": cat, "teacher": args.teacher, **res},
                                   ensure_ascii=False) + "\n")
        print(f"[{rec['idx']:02d}] {b['bundle_id']} ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
