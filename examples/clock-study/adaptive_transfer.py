"""Measure the frozen adaptive policy on the six published VOXL 2 recordings."""
import argparse
from collections import Counter
import json
from pathlib import Path

from replay_adaptive import HERE, POLICIES, challenge, native_pairs, read_exchange_pairs, summary


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
    args = parser.parse_args()
    print(json.dumps(replay(args.halo, args.case), indent=2))
