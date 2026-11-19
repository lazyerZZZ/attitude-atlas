"""Check a PX4/ROS sample clock mapping against an error budget using later events."""
import argparse
import csv
from itertools import groupby
import json
import math
from pathlib import Path
import sys

from clock_model import fit, percentile95, relative_times


def read_events(path):
    with Path(path).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        fields = ("px4_sample_us", "ros_sample_us")
        if not set(fields).issubset(reader.fieldnames or ()):
            raise ValueError("Expected px4_sample_us and ros_sample_us in the event CSV")
        pairs = []
        for index, row in enumerate(reader, start=2):
            values = [row.get(k) for k in fields]
            if not all(v and v.isascii() and v.isdecimal() and int(v) > 0 for v in values):
                raise ValueError(f"Invalid positive integer timestamp at CSV row {index}")
            pairs.append(tuple(int(v) * 1000 for v in values))
    return pairs


def error_ms(model, events):
    origin, slope = model
    return percentile95([abs(y - (origin + slope*x)) / 1e6 for x, y in events])


def assess(pairs, budget_ms=0.25, window_s=10.0):
    if not all(math.isfinite(x) and x > 0 for x in (budget_ms, window_s)) or round(window_s * 1e9) < 1:
        raise ValueError("Use a finite positive budget and window")
    width = round(window_s * 1e9)
    if any(x1 <= x0 or y1 <= y0 for (x0, y0), (x1, y1) in zip(pairs, pairs[1:])):
        raise ValueError("Split non-increasing clocks before evaluation")
    windows = []
    history = []
    model = None
    candidate = None
    decisions = []
    relative = relative_times(pairs) if pairs else []
    for index, group in groupby(relative, key=lambda p: p[0] // width):
        events = list(group)
        item = {"index": index, "start_s": events[0][0] / 1e9, "end_s": events[-1][0] / 1e9,
                "pairs": len(events)}
        windows.append(item)
        if len(events) < 8 or events[-1][0] - events[0][0] < width * 0.7:
            candidate = None
            item["action"] = "insufficient_coverage"
            continue
        if model is None:
            history.append(events)
            item["action"] = "training"
            if len(history) == 2:
                model = fit(history[0] + history[1])
            continue
        residual = error_ms(model, events)
        item.update(p95_ms=residual, action="within_budget")
        if residual <= budget_ms:
            candidate = None
            continue
        item["action"] = "over_budget"
        if candidate and candidate[0] == index - 1:
            _, previous, trial = candidate
            trial_error = error_ms(trial, events)
            item["candidate_p95_ms"] = trial_error
            if trial_error <= budget_ms and trial_error <= residual / 2:
                model = trial
                item["action"] = "recalibrate"
                decisions.append({"candidate_start_s": previous[0][0] / 1e9,
                                  "decision_s": item["end_s"], "old_p95_ms": residual,
                                  "candidate_p95_ms": trial_error, "rate_ppm": trial[1] * 1e6})
                candidate = None
                continue
        candidate = (index, events, fit(events))
    scored = [w for w in windows if "p95_ms" in w]
    return {"budget_ms": budget_ms, "window_s": window_s, "windows": windows, "decisions": decisions,
            "scored_windows": len(scored), "over_budget_windows": sum(w["p95_ms"] > budget_ms for w in scored)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("events")
    parser.add_argument("--budget-ms", type=float, default=0.25)
    parser.add_argument("--window-s", type=float, default=10)
    args = parser.parse_args()
    print(json.dumps(assess(read_events(args.events), args.budget_ms, args.window_s), indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        sys.exit(f"Clock segmentation: {exc}")
