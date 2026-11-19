import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
const cli = fileURLToPath(new URL("../bin/check-case.mjs", import.meta.url));
test("CLI recomputes exported cases, accepts a replacement ROS message, and signals CI failures", (t) => {
  const temp = mkdtempSync(join(tmpdir(), "atlas-cli-"));
  t.after(() => rmSync(temp, { recursive: true, force: true }));
  const path = join(temp, "case.json");
  writeFileSync(
    path,
    JSON.stringify({
      schema: "attitude-atlas/comparison-v1",
      px4: [1, 0, 0, 0],
      ros: [0.5, 0.5, 0.5, 0.5],
      sharedClock: false,
      result: { rotationDeg: 0 },
    }),
  );
  const run = (args, input) =>
    spawnSync(process.execPath, [cli, path, ...args], {
      encoding: "utf8",
      input,
    });
  const fail = run(["--max-error-deg", "1"]);
  assert.equal(fail.status, 1);
  assert.equal(JSON.parse(fail.stdout).rotationDeg, 90);
  const pass = run(
    ["--max-error-deg", ".001", "--ros", "-"],
    "orientation: {x: 0, y: 0, z: 1, w: 1}",
  );
  assert.equal(pass.status, 0);
  assert.equal(JSON.parse(pass.stdout).withinLimit, true);
  assert.equal(run(["--ros", "-"], "bad data").status, 2);
  assert.equal(run(["--max-error-deg", "NaN"]).status, 2);
});
