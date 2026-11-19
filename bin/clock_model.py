"""Estimate a rate difference from integer-nanosecond observations."""
from math import ceil
from statistics import mean, median


def relative_times(pairs):
    x0, y0 = pairs[0]
    return [(x - x0, (y - y0) - (x - x0)) for x, y in pairs]


def fit(relative):
    xs, errors = zip(*relative)
    center = mean(xs)
    baseline = mean(errors)
    variance = sum((x - center) ** 2 for x in xs)
    if not variance:
        raise ValueError("A clock fit needs distinct PX4 sample times")
    rate = sum((x - center) * (e - baseline) for x, e in relative) / variance
    return baseline - rate * center, rate


def percentile95(values):
    return sorted(values)[ceil(0.95 * len(values)) - 1]


def holdout(relative):
    if len(relative) < 6:
        return None
    split = len(relative) * 2 // 3
    train, test = relative[:split], relative[split:]
    intercept, rate = fit(train)
    constant = mean(e for _, e in train)
    result = {"training_pairs": len(train), "evaluation_pairs": len(test)}
    for name, origin, slope in (("constant", constant, 0), ("affine", intercept, rate)):
        residuals = [abs(e - (origin + x * slope)) / 1e6 for x, e in test]
        result[name] = {"median_abs_ms": median(residuals), "p95_abs_ms": percentile95(residuals)}
    return result


def time_windows(relative, count=4):
    """Use equal-duration windows so higher recording rates get no extra windows."""
    span = relative[-1][0]
    groups = [[] for _ in range(count)]
    for x, e in relative:
        groups[min(count - 1, x * count // span)].append((x, e))
    windows = []
    for group in groups:
        if len(group) < 2:
            windows.append({"pairs": len(group), "rate_ppm": None})
            continue
        _, rate = fit(group)
        windows.append({"pairs": len(group), "start_s": group[0][0] / 1e9,
                        "end_s": group[-1][0] / 1e9, "rate_ppm": rate * 1e6})
    return windows


def clock_report(pairs):
    if len(pairs) < 2:
        return None
    if any(x <= prev_x for (prev_x, _), (x, _) in zip(pairs, pairs[1:])):
        raise ValueError("PX4 sample time repeated or reversed in recording order; split the capture")
    relative = relative_times(pairs)
    _, rate = fit(relative)
    return {"span_s": relative[-1][0] / 1e9,
            "rate_ppm": rate * 1e6,
            "offset_change_ms": relative[-1][1] / 1e6,
            "windows": time_windows(relative),
            "holdout": holdout(relative)}
