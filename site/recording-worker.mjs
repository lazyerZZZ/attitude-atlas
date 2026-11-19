import {
  readPx4Recording,
  readRosRecording,
  matchRecording,
  clockCalibration,
  recordingSummary,
  comparisonCsv,
  sampleCase,
} from "./recordings.mjs";
async function load(file, path) {
  if (file) {
    if (file.size > 16 * 1024 * 1024)
      throw Error("Each input must be at most 16 MiB.");
    return file.text();
  }
  const response = await fetch(new URL(path, import.meta.url));
  if (!response.ok) throw Error("Demo capture unavailable.");
  return response.text();
}
let recording;
self.onmessage = async ({ data }) => {
  try {
    if (data.exportCsv) {
      const { p, ros, result } = recording;
      self.postMessage({
        csv: new Blob([comparisonCsv(result, p.rows, ros)], {
          type: "text/csv",
        }),
      });
      return;
    }
    if (data.inspect !== undefined) {
      const { p, ros, result } = recording,
        row = result.rows[data.inspect];
      self.postMessage({
        index: data.inspect,
        row,
        sourceStamp: ros[row.ri].stampNs.toString(),
        selected:
          row.rotationDeg === null ? null : sampleCase(row, p.rows, ros),
      });
      return;
    }
    const [csv, yaml] = await Promise.all([
      load(data.px, "samples/roll-spike.csv"),
      load(data.ros, "samples/roll-spike.yaml"),
    ]);
    const p = readPx4Recording(csv),
      ros = readRosRecording(yaml),
      offset = data.anchor
        ? clockCalibration(data.anchor.px, data.anchor.ros, data.anchor.endPx, data.anchor.endRos)
        : null,
      result = matchRecording(p.rows, ros, data.skew, offset);
    recording = { p, ros, result };
    const times = Float64Array.from(
      ros,
      (r) => Number(r.stampNs - ros[0].stampNs) / 1e9,
    );
    const angles = Float64Array.from(result.rows, (r) => r.rotationDeg ?? NaN);
    self.postMessage(
      {
        times,
        angles,
        worstIndex: result.worst?.ri ?? 0,
        summary: recordingSummary(result, p.rows, ros),
        field: p.field,
        offsetNs: typeof offset === "bigint" ? offset.toString() : null,
        ratePpm: offset?.ratePpm ?? null,
        outside: result.rows.filter(r => r.outsideCalibration).length,
        worst: result.worst ? sampleCase(result.worst, p.rows, ros) : null,
      },
      [times.buffer, angles.buffer],
    );
  } catch (e) {
    self.postMessage({ error: e.message });
  }
};
