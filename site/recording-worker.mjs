import {
  readPx4Recording,
  readRosRecording,
  matchRecording,
  recordingSummary,
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
self.onmessage = async ({ data }) => {
  try {
    const [csv, yaml] = await Promise.all([
      load(data.px, "samples/roll-spike.csv"),
      load(data.ros, "samples/roll-spike.yaml"),
    ]);
    const p = readPx4Recording(csv),
      ros = readRosRecording(yaml),
      result = matchRecording(p.rows, ros, data.skew);
    self.postMessage({
      summary: recordingSummary(result, p.rows, ros),
      field: p.field,
      worst: result.worst ? sampleCase(result.worst, p.rows, ros) : null,
    });
  } catch (e) {
    self.postMessage({ error: e.message });
  }
};
