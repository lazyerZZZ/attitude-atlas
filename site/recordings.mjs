import { comparisonCase } from "./cases.mjs";
import { parseTrack } from "./frames.mjs";
import { readMessage, compareAttitudes } from "./messages.mjs";

export function readPx4Recording(csv) {
  const frames = parseTrack(csv);
  // Use one time basis across the recording, even when a few sample
  // timestamps are unavailable. Do not alternate between the two clocks.
  const sampled = frames.every((f) => f.sampleUs > 0);
  const field = sampled ? "timestamp_sample" : "timestamp";
  const rows = frames.map((f, i) => {
    const us = sampled ? f.sampleUs : f.timestampUs;
    if (
      i &&
      us <= (sampled ? frames[i - 1].sampleUs : frames[i - 1].timestampUs)
    )
      throw Error("PX4 " + field + " must increase at sample " + (i + 1) + ".");
    return {
      q: f.q,
      stampNs: BigInt(us) * 1000n,
      source: { q: f.raw, [field]: us },
    };
  });
  return { rows, field };
}
export function readRosRecording(yaml) {
  const messages = [];
  for (const doc of yaml.split(/^---[ \t]*(?:#[^\n]*)?\r?$/m)) {
    if (!doc.trim()) continue;
    const n = messages.length + 1;
    try {
      const row = readMessage(doc, "ros");
      if (row.stampNs === null) throw Error("Missing nonzero header.stamp.");
      const prev = messages.at(-1);
      if (prev && row.stampNs <= prev.stampNs)
        throw Error(
          "header.stamp must increase. Split clock restarts into separate captures.",
        );
      if (prev && (row.world !== prev.world || row.child !== prev.child))
        throw Error("Frame IDs changed. Select a single frame pair.");
      messages.push(row);
    } catch (e) {
      throw Error("ROS message " + n + " · " + e.message);
    }
  }
  if (!messages.length) throw Error("No stamped ROS messages in capture.");
  return messages;
}

export function matchRecording(px4, ros, maxSkewMs) {
  if (
    !Number.isFinite(maxSkewMs) ||
    maxSkewMs < 0 ||
    !Number.isSafeInteger(Math.round(maxSkewMs * 1e6))
  )
    throw Error("Maximum skew must be a finite nonnegative millisecond value.");
  const limit = BigInt(Math.round(maxSkewMs * 1e6));
  const rows = [];
  let cursor = 0,
    matched = 0,
    worst = null;
  for (const [ri, message] of ros.entries()) {
    const target = message.stampNs;
    while (
      cursor + 1 < px4.length &&
      px4[cursor].stampNs + px4[cursor + 1].stampNs < 2n * target
    )
      cursor++;
    const skew = target - px4[cursor].stampNs;
    const row = {
      ri,
      pi: cursor,
      skewMs: Number(skew) / 1e6,
      rotationDeg: null,
    };
    if (skew <= limit && skew >= -limit) {
      row.rotationDeg = compareAttitudes(px4[cursor], message).rotationDeg;
      if (!worst || row.rotationDeg > worst.rotationDeg) worst = row;
      matched++;
    }
    rows.push(row);
  }
  return { rows, matched, unmatched: rows.length - matched, worst };
}

export function recordingSummary(result, px4, ros) {
  const matched = result.rows.filter((row) => row.rotationDeg !== null);
  const angles = matched.map((row) => row.rotationDeg).sort((a, b) => a - b);
  const p95 = angles.length
    ? angles[Math.ceil(0.95 * angles.length) - 1]
    : null;
  return {
    px4Samples: px4.length,
    rosSamples: ros.length,
    matched: matched.length,
    unmatched: result.unmatched,
    coverage: matched.length / ros.length,
    distinctPx4: new Set(matched.map((r) => r.pi)).size,
    p95Deg: p95,
    maxDeg: result.worst?.rotationDeg ?? null,
  };
}
export function sampleCase(row, px4, ros) {
  if (!row || row.rotationDeg === null) throw Error("Select a matched sample.");
  return comparisonCase(px4[row.pi], ros[row.ri], true);
}

export function comparisonCsv(result, px4, ros) {
  const header =
    "status,ros_sample,nearest_px4_sample,ros_stamp_ns,px4_stamp_ns,ros_minus_px4_ms,rotation_error_deg";
  const rows = result.rows.map((row) =>
    [
      row.rotationDeg === null ? "unmatched" : "matched",
      row.ri + 1,
      row.pi + 1,
      ros[row.ri].stampNs.toString(),
      px4[row.pi].stampNs.toString(),
      row.skewMs,
      row.rotationDeg ?? "",
    ].join(","),
  );
  return [header, ...rows].join("\n") + "\n";
}
