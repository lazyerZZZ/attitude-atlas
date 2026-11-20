"""Isolate nomination and candidate acceptance thresholds on one recorded exchange stream."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bin"))
from exchange_replay import read_exchange_pairs
from segment_clocks import assess


def factorial(pairs, budget_ms):
    rows = []
    for policy in ("confirmed", "headroom"):
        for limit in (budget_ms, budget_ms / 2):
            report = assess(pairs, budget_ms, policy=policy, candidate_limit_ms=limit)
            rows.append({"nomination_ms": budget_ms if policy == "confirmed" else budget_ms / 2,
                         "acceptance_ms": limit, **report["evaluation"],
                         "switch_s": [d["decision_s"] for d in report["decisions"]]})
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bag", type=Path)
    parser.add_argument("--budget-ms", type=float, default=0.25)
    args = parser.parse_args()
    print(json.dumps({k: factorial(p, args.budget_ms) for k, p in read_exchange_pairs(args.bag).items()}, indent=2))
