import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL("../", import.meta.url));
function run(args) {
  return spawnSync(
    process.execPath,
    [
      "bin/check-recording.mjs",
      "site/samples/roll-spike.csv",
      "site/samples/roll-spike.yaml",
      ...args,
    ],
    { cwd: root, encoding: "utf8" },
  );
}
test("recording CI distinguishes tolerances, missing matches, and invalid configuration", () => {
  const fail = run([
    "--shared-clock",
    "--max-error-deg",
    "2",
    "--min-coverage-pct",
    "100",
  ]);
  assert.equal(fail.status, 1);
  assert.equal(JSON.parse(fail.stdout).failures.length, 2);
  assert.equal(
    run(["--shared-clock", "--max-error-deg", "90", "--min-coverage-pct", "95"])
      .status,
    0,
  );
  assert.equal(run(["--shared-clock", "--max-skew-ms", "0"]).status, 1);
  assert.equal(run(["--shared-clock", "--min-coverage-pct", "-1"]).status, 2);
  assert.equal(run([]).status, 2);
});
test("a conflicting case export leaves existing reports intact and rolls back new rows", async (t) => {
  const { mkdtemp, writeFile, readFile, readdir, rm } = await import(
    "node:fs/promises"
  );
  const { tmpdir } = await import("node:os");
  const { join } = await import("node:path");
  const dir = await mkdtemp(join(tmpdir(), "atlas-export-"));
  t.after(() => rm(dir, { recursive: true, force: true }));
  const existing = join(dir, "case.json");
  await writeFile(existing, "prior report");
  const r = run([
    "--shared-clock",
    "--rows-out",
    join(dir, "rows.csv"),
    "--case-out",
    existing,
  ]);
  assert.equal(r.status, 2);
  assert.equal(await readFile(existing, "utf8"), "prior report");
  assert.deepEqual(await readdir(dir), ["case.json"]);
});
