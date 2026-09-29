"""Do a teacher's labels follow the facts the bundle shows? A sanity check, not ground truth.

Each check compares bundles where a fact is visible to the labeller against bundles where it is
not. The facts come from the scenario, but a bundle only counts as showing one when the attribute
carrying it is ANSWERED or PARTIAL, since the labeller never sees the scenario. A gap in the right
direction says a teacher reads that fact; it does not say the scores are right.

    python -m datagen.check                                  # every labels*.jsonl in data/
    python -m datagen.check --data data/pilot2/distilabel    # another run's output
"""
import argparse
import json
import statistics as st
from pathlib import Path


def shown(b: dict, attribute: str) -> bool:
    return b["attributes"][attribute]["status"] in ("ANSWERED", "PARTIAL")


def facts(s: dict, b: dict) -> dict:
    host = (shown(b, "permissions") and s["privileged"]) or \
           (shown(b, "mounts") and bool({"docker_socket", "host_root"} & set(s["mounts"])))
    baked = (not s["gateway_fronted"] and shown(b, "credential_provenance")
             and any(c["provenance"] == "baked" and c["class"] != "secret_ref" for c in s["credentials"]))
    return {
        "host_reach": host,                       # containment: privileged, Docker socket or host /
        "priv_root": shown(b, "permissions") and s["privileged"] and s["run_as"] == "root",
        "baked_secret": baked,                    # identity: the baked_secret hard cap's condition
        "no_creds": b["attributes"]["credential_inventory"]["status"] == "ABSENT",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    DATA = Path(ap.parse_args().data)
    scen = {r["bundle_id"]: r for r in map(json.loads, (DATA / "scenarios.jsonl").open())}
    bundles = {bid: json.loads((DATA / "bundles" / f"{bid}.json").read_text()) for bid in scen}
    F = {bid: facts(scen[bid]["scenario"], bundles[bid]) for bid in scen}
    labels = [json.loads(l) for p in sorted(DATA.glob("labels*.jsonl")) for l in p.open() if l.strip()]
    teachers = sorted({l["teacher"] for l in labels})
    med = {(l["teacher"], l["category"], l["bundle_id"]): l["median"] for l in labels if l["outcome"] == "SCORED"}
    spread = {t: [max(x["score"] for x in l["samples"] if x["valid"]) - min(x["score"] for x in l["samples"] if x["valid"])
                  for l in labels if l["teacher"] == t and l["outcome"] == "SCORED"] for t in teachers}

    def gap(t, cat, fact):
        yes = [v for (tt, c, bid), v in med.items() if tt == t and c == cat and F[bid][fact]]
        no = [v for (tt, c, bid), v in med.items() if tt == t and c == cat and not F[bid][fact]]
        return f"{st.mean(yes):.1f} vs {st.mean(no):.1f}" if yes and no else "n/a"

    rows = [
        ("containment: host reach shown vs not (lower first = reads it)", lambda t: gap(t, "containment", "host_reach")),
        ("containment: privileged+root scored <= 2 (anchor is 1)",
         lambda t: "{}/{}".format(*(lambda v: (sum(x <= 2 for x in v), len(v)))(
             [v for (tt, c, bid), v in med.items() if tt == t and c == "containment" and F[bid]["priv_root"]]))),
        ("identity: baked secret shown vs not (lower first = reads it)", lambda t: gap(t, "identity", "baked_secret")),
        ("identity: no credentials vs some (higher first = reads it)", lambda t: gap(t, "identity", "no_creds")),
        ("mean spread across a teacher's own samples", lambda t: f"{st.mean(spread[t]):.2f}"),
    ]
    print("| check | " + " | ".join(teachers) + " |\n|---|" + "---|" * len(teachers))
    for name, fn in rows:
        print(f"| {name} | " + " | ".join(fn(t) for t in teachers) + " |")
    print("\nPairwise agreement on medians (within 1 point):")
    for i, a in enumerate(teachers):
        for b in teachers[i + 1:]:
            for cat in ("identity", "containment"):
                both = [(med[(a, cat, bid)], med[(b, cat, bid)]) for bid in scen if (a, cat, bid) in med and (b, cat, bid) in med]
                if both:
                    print(f"  {a} ~ {b} {cat}: {sum(abs(x - y) <= 1 for x, y in both)}/{len(both)}")


if __name__ == "__main__":
    main()
