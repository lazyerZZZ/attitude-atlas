"""Recompute the two public clock audits from a local upstream data checkout."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "bin"))
from pair_clocks import join, read_bag, read_ulog, sync_report, timing_report


def verified_file(root, entry):
    path = root / entry["path"]
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != entry["sha256"]:
        raise ValueError(f"Input hash mismatch for {path}")
    return path


def equivalent(actual, expected):
    if isinstance(expected, dict):
        return (isinstance(actual, dict) and actual.keys() == expected.keys()
                and all(equivalent(actual[k], v) for k, v in expected.items()))
    if isinstance(expected, list):
        return (isinstance(actual, list) and len(actual) == len(expected)
                and all(equivalent(a, b) for a, b in zip(actual, expected)))
    if isinstance(expected, float):
        return isinstance(actual, (float, int)) and math.isclose(actual, expected, abs_tol=1e-9, rel_tol=1e-10)
    return actual == expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_checkout", type=Path)
    parser.add_argument("--check", action="store_true", help="Verify published results and cross-flight negative controls")
    args = parser.parse_args()
    manifest = json.loads((HERE / "sources.json").read_text())
    reports, px_logs, bags = {}, {}, {}
    for name, files in manifest["captures"].items():
        px = read_ulog(verified_file(args.data_checkout, files["ulg"]))
        ros, statuses = read_bag(verified_file(args.data_checkout, files["mcap"]),
                                 "/fmu/out/vehicle_attitude", "/fmu/out/timesync_status")
        anchors, report = join(px, ros)
        if not anchors:
            raise ValueError(f"No shared events in {name}")
        report.update(timing_report(anchors))
        report["timesync"] = sync_report(statuses, anchors)
        reports[name] = report
        px_logs[name], bags[name] = px, ros
    if args.check:
        for px_name, px in px_logs.items():
            for bag_name, ros in bags.items():
                if px_name != bag_name and join(px, ros)[0]:
                    raise ValueError(f"Unexpected shared event between {px_name} and {bag_name}")
        if not equivalent(reports, json.loads((HERE / "results.json").read_text())):
            raise ValueError("Measured clock metrics differ from the published results")
        print("Both capture reports verified. Both cross-flight controls returned zero shared events.")
    else:
        print(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()
