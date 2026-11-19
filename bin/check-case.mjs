#!/usr/bin/env node
import { readFile } from "node:fs/promises";
import { readFileSync } from "node:fs";
import { parseArgs } from "node:util";
import { openCase } from "../site/cases.mjs";
import { compareAttitudes, readMessage } from "../site/messages.mjs";

const usage =
  "Usage: node bin/check-case.mjs CASE.json [--ros MESSAGE.yaml|-] [--max-error-deg DEGREES]";
async function main() {
  const { values, positionals } = parseArgs({
    allowPositionals: true,
    options: {
      ros: { type: "string" },
      "max-error-deg": { type: "string" },
      help: { type: "boolean", short: "h" },
    },
  });
  if (values.help) {
    console.log(usage);
    return;
  }
  if (positionals.length !== 1) throw Error(usage);
  const limitText = values["max-error-deg"];
  const limit = limitText === undefined ? null : Number(limitText);
  if (
    limitText !== undefined &&
    (!limitText.trim() || !Number.isFinite(limit) || limit < 0 || limit > 180)
  )
    throw Error("--max-error-deg must be a number from 0 to 180.");
  const { px4, ros, sharedClock } = openCase(
    JSON.parse(await readFile(positionals[0], "utf8")),
  );
  let observed = ros;
  if (values.ros !== undefined) {
    const text =
      values.ros === "-"
        ? readFileSync(0, "utf8")
        : await readFile(values.ros, "utf8");
    observed = readMessage(text, "ros");
  }
  const {
    rotationDeg,
    forwardDeg,
    bodyAxisErrorsDeg,
    timeOffsetMs,
    expected,
    observed: actual,
  } = compareAttitudes(px4, observed, sharedClock && values.ros === undefined);
  const withinLimit = limit === null ? null : rotationDeg <= limit;
  console.log(
    JSON.stringify(
      {
        rotationDeg,
        forwardDeg,
        bodyAxisErrorsDeg,
        timeOffsetMs,
        expectedRosXYZW: expected,
        observedRosXYZW: actual,
        limitDeg: limit,
        withinLimit,
      },
      null,
      2,
    ),
  );
  if (withinLimit === false) process.exitCode = 1;
}
main().catch((error) => {
  console.error(error.message);
  process.exitCode = 2;
});
