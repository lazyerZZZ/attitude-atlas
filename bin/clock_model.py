"""Estimate a rate difference from integer-nanosecond observations."""
from statistics import mean


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


def clock_report(pairs):
    if len(pairs) < 2:
        return None
    if any(x <= prev_x for (prev_x, _), (x, _) in zip(pairs, pairs[1:])):
        raise ValueError("PX4 sample time repeated or reversed in recording order; split the capture")
    relative = relative_times(pairs)
    _, rate = fit(relative)
    return {"span_s": relative[-1][0] / 1e9,
            "rate_ppm": rate * 1e6,
            "offset_change_ms": relative[-1][1] / 1e6}
