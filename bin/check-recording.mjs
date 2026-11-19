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
  "Usage: node bin/check-recording.mjs PX4.csv ROS.yaml --shared-clock [--max-skew-ms 20] [--case-out NEW.json] [--rows-out NEW.csv]";
async function main() {
  const { values, positionals } = parseArgs({
    allowPositionals: true,
    options: {
      "shared-clock": { type: "boolean" },
      "max-skew-ms": { type: "string", default: "20" },
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
  const result = matchRecording(px4.rows, ros, maxSkewMs);
  console.log(
    JSON.stringify(
      {
        ...recordingSummary(result, px4.rows, ros),

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
  if (!result.matched) process.exitCode = 1;
}
main().catch((e) => {
  console.error(e.message);
  process.exitCode = 2;
});
