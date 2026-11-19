"""Replay both hardware corpora and test every off-diagonal log pairing."""
import argparse
import json
from pathlib import Path

from reproduce import HERE, equivalent, verified_file
from pair_clocks import join, matched_land_states, read_bag, read_flight, timing_report
from segment_clocks import assess


def measure(anchors, counts, platform, states):
    sample = timing_report(anchors)["sample_clock"]
    if not sample or sample["rate_ppm"] is None:
        raise ValueError("This reference capture has no measurable sample-clock rate")
    data = [(a.px4_us * 1000, a.ros_us * 1000) for a in anchors]
    report = assess(data)
    return {**platform, **counts, "land_states": matched_land_states(anchors, states),
            "span_s": sample["span_s"], "rate_ppm": sample["rate_ppm"],
            "offset_change_ms": sample["offset_change_ms"],
            "verdict": report["verdict"], "scored_windows": report["scored_windows"],
            "decisions_s": [d["decision_s"] for d in report["decisions"]],
            "evaluation": report["evaluation"]}


def compare(original_root, halo_root):
    cases, ulgs, bags = {}, {}, {}
    for manifest, root in (("sources.json", original_root), ("halo-sources.json", halo_root)):
        for name, files in json.loads((HERE / manifest).read_text())["captures"].items():
            ulgs[name], platform, states = read_flight(verified_file(root, files["ulg"]))
            entry = files["db3"] if "db3" in files else files["mcap"]
            bags[name], _ = read_bag(verified_file(root, entry), "/fmu/out/vehicle_attitude", "/fmu/out/timesync_status")
            anchors, counts = join(ulgs[name], bags[name])
            cases[name] = measure(anchors, counts, platform, states)
    negatives = 0
    for name, px in ulgs.items():
        for other, ros in bags.items():
            if name == other:
                continue
            if join(px, ros)[0]:
                raise ValueError(f"Unexpected shared attitude between {name} and {other}")
            negatives += 1
    return {"budget_ms": 0.25, "window_s": 10, "zero_match_controls": negatives, "captures": cases}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_checkout", type=Path)
    parser.add_argument("halo_checkout", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = compare(args.original_checkout, args.halo_checkout)
    if args.check:
        if not equivalent(result, json.loads((HERE / "hardware-results.json").read_text())):
            raise SystemExit("Hardware comparison differs from the published results")
        print(f"Verified {len(result['captures'])} paired captures and {result['zero_match_controls']} negative controls.")
    else:
        print(json.dumps(result, indent=2))
