"""Validate clock calibration on native attitude events in the TU Delft flight records."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from fetch_delft import matches_entry

from reproduce import HERE, equivalent
from replay_adaptive import summary
from segment_clocks import POLICIES
from alarm_controls import challenge
from pair_clocks import join, matched_land_states, overlap_report, read_bag, read_flight
from clock_model import clock_report


def member(root, entry):
    path = root / entry["path"]
    if not matches_entry(path, entry):
        raise ValueError(f"Unexpected file contents: {path.name}")
    return path


def control_counts(pairs):
    counts = {p: defaultdict(Counter) for p in POLICIES}
    delays = {p: [] for p in POLICIES}
    for trial in challenge(pairs, policies=POLICIES, phases=(0, .125, .25, .5, .75, .875), negative_pulses=True):
        policy = trial["policy"]
        counts[policy][trial["scenario"]][trial["outcome"]] += 1
        if trial["outcome"] == "TP":
            delays[policy].append(min(t for t in trial["alarm_times_s"] if t >= trial["onset_s"]) - trial["onset_s"])
    return {p: {"outcomes": counts[p], "max_detected_delay_s": max(delays[p], default=None)} for p in POLICIES}


def replay(root, cases):
    flights, logs, bags = {}, {}, {}
    for name, entries in cases.items():
        px, board, states = read_flight(member(root, entries["ulg"]))
        ros, _ = read_bag(member(root, entries["mcap"]), "/fmu/out/vehicle_attitude", "/fmu/out/timesync_status")
        anchors, counts = join(px, ros)
        if not anchors:
            raise ValueError(f"No matching attitude samples in {name}")
        pairs = [(a.px4_us * 1000, a.ros_us * 1000) for a in anchors]
        drift = clock_report(pairs)
        flights[name] = {**board, **counts, "land_states": matched_land_states(anchors, states),
                         "overlap": overlap_report(anchors), "rate_ppm": drift["rate_ppm"],
                         "endpoint_offset_change_ms": drift.get("offset_change_ms"),
                         "comparison": summary(pairs), "injected_controls": control_counts(pairs)}
        logs[name], bags[name] = px, ros
    negatives = {}
    for name, px in logs.items():
        for other, ros in bags.items():
            if name != other:
                wrong, _ = join(px, ros)
                negatives[f"{name}/{other}"] = len(wrong)
                if wrong:
                    raise ValueError(f"Cross-flight match in {name}/{other}")
    return {"flights": flights, "wrong_flight_matches": negatives}


if __name__ == "__main__":
    cases = json.loads((HERE / "delft-sources.json").read_text())["captures"]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument("--case", choices=cases)
    parser.add_argument("--check", action="store_true", help="Check all measured values against the published replay")
    args = parser.parse_args()
    measured = replay(args.data, {args.case: cases[args.case]} if args.case else cases)
    if args.check:
        expected = json.loads((HERE / "delft-results.json").read_text())
        actual = measured["flights"][args.case] if args.case else measured
        expected = expected["flights"][args.case] if args.case else expected
        if not equivalent(actual, expected):
            raise SystemExit("Delft replay differs from the published measurements")
    print(json.dumps(measured, indent=2))
