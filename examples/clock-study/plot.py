"""Render two --events-out CSVs as elapsed-time plots (requires matplotlib)."""
import argparse
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def draw(path, axis, title):
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    px = [int(r["px4_sample_us"]) * 1000 for r in rows]
    elapsed = [(x - px[0]) / 1e9 for x in px]
    for field, scale, color, label in (
        ("mcap_log_ns", 1, "#798e9a", "MCAP receive"),
        ("ros_sample_us", 1000, "#00659a", "ROS sample"),
    ):
        offsets = [int(row[field]) * scale - x for row, x in zip(rows, px)]
        drift = [(value - offsets[0]) / 1e6 for value in offsets]
        axis.scatter(elapsed, drift, s=4, alpha=0.55, linewidths=0, color=color, label=label)
    axis.set_title(title, loc="left", weight="bold")
    axis.set_ylabel("Offset change (ms)")
    axis.set_xlabel("Elapsed PX4 time (s)")
    axis.grid(axis="y", alpha=.2)
    axis.spines[["right", "top"]].set_visible(False)
    axis.legend(loc="upper left", ncol=2, frameon=False, markerscale=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("reference", "ground_effect", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    figure, axes = plt.subplots(2, 1, figsize=(7, 5.8), layout="constrained", sharey=True)
    draw(args.reference, axes[0], "Reference flight")
    draw(args.ground_effect, axes[1], "Ground-effect test")
    figure.savefig(args.output, dpi=160)
