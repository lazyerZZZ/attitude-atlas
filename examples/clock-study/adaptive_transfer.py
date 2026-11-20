"""Measure the frozen adaptive policy on the six published VOXL 2 recordings."""
import argparse
from collections import Counter
import json
from pathlib import Path

from reproduce import HERE, equivalent
from alarm_controls import challenge
from exchange_replay import read_exchange_pairs
from replay_adaptive import native_pairs, summary
from segment_clocks import POLICIES


def replay(root, selected=None):
    captures = json.loads((HERE / "holdout-sources.json").read_text())["halo"]["captures"]
    if selected is not None and selected not in captures:
        raise ValueError("Unknown VOXL capture")
    cases = {}
    counts = {policy: Counter() for policy in POLICIES}
    for name, files in captures.items():
        if selected and name != selected:
            continue
        pairs, path = native_pairs(root, files, "db3")
        cases[name] = {"native": summary(pairs)}
        for trial in challenge(pairs, policies=POLICIES):
            counts[trial["policy"]][trial["outcome"]] += 1
        for protocol, exchanges in read_exchange_pairs(path).items():
            if (exchanges[-1][0] - exchanges[0][0]) >= 180e9:
                cases[name].setdefault("long_exchanges", {})[str(protocol)] = summary(exchanges)
    return {"cases": cases, "controls": counts}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("halo", type=Path)
    parser.add_argument("--case")
    parser.add_argument("--check", action="store_true", help="Verify recorded results and pooled controls")
    args = parser.parse_args()
    result = replay(args.halo, args.case)
    if args.check:
        expected = json.loads((HERE / "adaptive-transfer.json").read_text())
        if args.case:
            actual = result["cases"][args.case]
            expected = expected["cases"][args.case]
        else:
            actual = result
        if not equivalent(actual, expected):
            raise SystemExit("Adaptive hardware transfer results differ")
    print(json.dumps(result, indent=2))
