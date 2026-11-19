#!/usr/bin/env node
import { saveReports } from "./save-reports.mjs";
import { readFile } from "node:fs/promises";
import { readPx4Input } from "./px4-input.mjs";
import { parseArgs } from "node:util";
import {
  readPx4Recording,
  readRosRecording,
  matchRecording,
  clockCalibration,
  recordingSummary,
  comparisonCsv,
  sampleCase,
} from "../site/recordings.mjs";
const usage =
  "Usage: node bin/check-recording.mjs PX4.csv|flight.ulg ROS.yaml (--shared-clock | --px4-anchor-us US --ros-anchor-ns NS [--px4-end-us US --ros-end-ns NS]) [--max-skew-ms 20] [--case-out NEW.json] [--rows-out NEW.csv] [--max-error-deg N] [--min-coverage-pct N]";
async function main() {
  const { values, positionals } = parseArgs({
    allowPositionals: true,
    options: {
      "px4-anchor-us": { type: "string" },
      "ros-anchor-ns": { type: "string" },
      "px4-end-us": { type: "string" },
      "ros-end-ns": { type: "string" },
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
  const anchored =
    values["px4-end-us"] !== undefined || values["ros-end-ns"] !== undefined ||
    values["px4-anchor-us"] !== undefined ||
    values["ros-anchor-ns"] !== undefined;
  if (positionals.length !== 2 || anchored === Boolean(values["shared-clock"]))
    throw Error(usage);
  const offset = anchored
    ? clockCalibration(values["px4-anchor-us"], values["ros-anchor-ns"], values["px4-end-us"], values["ros-end-ns"])
    : null;
  const csv = await readPx4Input(positionals[0]),
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
  const result = matchRecording(px4.rows, ros, maxSkewMs, offset);
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

        rosMinusPx4ClockOffsetNs: typeof offset === "bigint" ? offset.toString() : null,
        calibratedRatePpm: offset?.ratePpm ?? null,
        outsideCalibration: result.rows.filter(row => row.outsideCalibration).length,
        px4TimeField: px4.field,
        maxSkewMs,

        worst: result.worst,
      },
      null,
      2,
    ),
  );
  const reports = [];
  if (values["rows-out"])
    reports.push([values["rows-out"], comparisonCsv(result, px4.rows, ros)]);
  if (values["case-out"] && result.worst)
    reports.push([
      values["case-out"],
      JSON.stringify(sampleCase(result.worst, px4.rows, ros), null, 2) + "\n",
    ]);
  await saveReports(reports);
  if (failures.length) process.exitCode = 1;
}
main().catch((e) => {
  console.error(e.message);
  process.exitCode = 2;
});
