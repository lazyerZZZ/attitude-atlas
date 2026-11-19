#!/usr/bin/env node
import { readFile, writeFile } from "node:fs/promises";
import { parseArgs } from "node:util";
import {
  readPx4Recording,
  readRosRecording,
  matchRecording,
  recordingSummary,
  comparisonCsv,
  sampleCase,
} from "../site/recordings.mjs";
const usage =
  "Usage: node bin/check-recording.mjs PX4.csv ROS.yaml --shared-clock [--max-skew-ms 20] [--case-out NEW.json] [--rows-out NEW.csv] [--max-error-deg N] [--min-coverage-pct N]";
async function main() {
  const { values, positionals } = parseArgs({
    allowPositionals: true,
    options: {
      "shared-clock": { type: "boolean" },
      "max-skew-ms": { type: "string", default: "20" },
      "max-error-deg": { type: "string" },
      "min-coverage-pct": { type: "string" },
      "rows-out": { type: "string" },
      "case-out": { type: "string" },
      help: { type: "boolean", short: "h" },
    },
  });
  if (values.help) {
    console.log(usage);
    return;
  }
  if (positionals.length !== 2 || !values["shared-clock"]) throw Error(usage);
  const csv = await readFile(positionals[0], "utf8"),
    yaml = await readFile(positionals[1], "utf8");
  const px4 = readPx4Recording(csv),
    ros = readRosRecording(yaml);
  const maxSkewMs = Number(values["max-skew-ms"]);
  if (!values["max-skew-ms"].trim()) throw Error("Enter a maximum skew.");
  function threshold(name, upper) {
    const text = values[name];
    if (text === undefined) return null;
    const value = Number(text);
    if (!text.trim() || !Number.isFinite(value) || value < 0 || value > upper)
      throw Error("--" + name + " must be between 0 and " + upper + ".");
    return value;
  }
  const errorLimitDeg = threshold("max-error-deg", 180),
    minCoveragePct = threshold("min-coverage-pct", 100);
  const result = matchRecording(px4.rows, ros, maxSkewMs);
  const summary = recordingSummary(result, px4.rows, ros);
  const failures = [];
  if (!result.matched) failures.push("No matched samples");
  if (
    errorLimitDeg !== null &&
    summary.maxDeg !== null &&
    summary.maxDeg > errorLimitDeg
  )
    failures.push("Peak rotation exceeds tolerance");
  if (minCoveragePct !== null && 100 * summary.coverage < minCoveragePct)
    failures.push("Matched ROS coverage is below minimum");
  console.log(
    JSON.stringify(
      {
        ...summary,
        errorLimitDeg,
        minCoveragePct,
        failures,

        px4TimeField: px4.field,
        maxSkewMs,

        worst: result.worst,
      },
      null,
      2,
    ),
  );
  if (values["rows-out"])
    await writeFile(values["rows-out"], comparisonCsv(result, px4.rows, ros), {
      flag: "wx",
    });
  if (values["case-out"] && result.worst)
    await writeFile(
      values["case-out"],
      JSON.stringify(sampleCase(result.worst, px4.rows, ros), null, 2) + "\n",
      { flag: "wx" },
    );
  if (failures.length) process.exitCode = 1;
}
main().catch((e) => {
  console.error(e.message);
  process.exitCode = 2;
});
