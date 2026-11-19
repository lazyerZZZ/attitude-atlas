#!/usr/bin/env node
import { readFile } from "node:fs/promises";
import { parseArgs } from "node:util";
import {
  readPx4Recording,
  readRosRecording,
  matchRecording,
} from "../site/recordings.mjs";
const usage =
  "Usage: node bin/check-recording.mjs PX4.csv ROS.yaml --shared-clock [--max-skew-ms 20]";
async function main() {
  const { values, positionals } = parseArgs({
    allowPositionals: true,
    options: {
      "shared-clock": { type: "boolean" },
      "max-skew-ms": { type: "string", default: "20" },
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
        px4Samples: px4.rows.length,
        rosSamples: ros.length,
        px4TimeField: px4.field,
        maxSkewMs,
        matched: result.matched,
        unmatched: result.unmatched,
        worst: result.worst,
      },
      null,
      2,
    ),
  );
  if (!result.matched) process.exitCode = 1;
}
main().catch((e) => {
  console.error(e.message);
  process.exitCode = 2;
});
