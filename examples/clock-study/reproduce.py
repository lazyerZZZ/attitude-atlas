"""Recompute the two public clock audits from a local upstream data checkout."""
import argparse
import hashlib
import json
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_checkout", type=Path)
    args = parser.parse_args()
    manifest = json.loads((HERE / "sources.json").read_text())
    reports = {}
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
    print(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()
