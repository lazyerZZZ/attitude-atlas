"""Replay the adaptive policy on the original ground-effect and VOXL 2 development records."""
import argparse
from collections import Counter
import json
from pathlib import Path

from reproduce import HERE, equivalent, verified_file
from alarm_controls import challenge
from exchange_replay import read_exchange_pairs
from pair_clocks import join, read_bag, read_ulog
from segment_clocks import POLICIES, assess, compare_policies
from threshold_study import factorial


def native_pairs(root, files, kind):
    px = read_ulog(verified_file(root, files["ulg"]))
    path = verified_file(root, files[kind])
    rows, _ = read_bag(path, "/fmu/out/vehicle_attitude", "/fmu/out/timesync_status")
    anchors, _ = join(px, rows)
    if not anchors:
        raise ValueError("No unique native matches")
    return [(a.px4_us * 1000, a.ros_us * 1000) for a in anchors], path


def summary(pairs):
    result = compare_policies(pairs, policies=POLICIES)
    return {"scored_event_sha256": result["scored_event_sha256"],
            "policies": {p: {"pairs": r["evaluation"]["pairs"],
                              "p95_ms": r["evaluation"]["adaptive_p95_ms"],
                              "over_budget_pairs": r["over_budget_pairs"],
                              "switches": len(r["switches"])} for p, r in result["policies"].items()}}


def run(original, halo):
    ground_files = json.loads((HERE / "sources.json").read_text())["captures"]["ground_effect"]
    halo_files = json.loads((HERE / "holdout-sources.json").read_text())["halo"]["captures"]["115317_D0015"]
    ground, _ = native_pairs(original, ground_files, "mcap")
    native, path = native_pairs(halo, halo_files, "db3")
    pairs = read_exchange_pairs(path)[0]
    report = assess(pairs, policy="headroom")
    rejects = [dict(window=w["index"], old_p95_ms=w["p95_ms"], candidate_p95_ms=w["candidate_p95_ms"])
               for w in report["windows"] if "candidate_checks" in w and
               w["candidate_checks"]["halves_error"] and 0.125 < w["candidate_p95_ms"] <= 0.25]
    trials = challenge(native, policies=POLICIES, phases=(0, .125, .25, .5, .75, .875))
    return {"ground_native": summary(ground), "voxl_native": summary(native),
            "voxl_exchange": summary(pairs), "factorial": factorial(pairs, .25),
            "rejected_only_by_tight_limit": rejects,
            "native_schedule_controls": {p: dict(Counter(t["outcome"] for t in trials if t["policy"] == p))
                                         for p in POLICIES}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("halo", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    measured = run(args.original, args.halo)
    if args.check:
        if measured["ground_native"]["policies"]["adaptive"]["p95_ms"] > .25:
            raise SystemExit("Adaptive ground-effect P95 exceeds 0.25 ms")
        if not equivalent(measured, json.loads((HERE / "adaptive-results.json").read_text())):
            raise SystemExit("Adaptive replay differs from published measurements")
    else:
        print(json.dumps(measured, indent=2))
