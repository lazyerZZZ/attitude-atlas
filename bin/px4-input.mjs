import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, join, resolve } from "node:path";
const execute = promisify(execFile);
export async function readPx4Input(file) {
  if (!file.toLowerCase().endsWith(".ulg")) return readFile(file, "utf8");
  const directory = await mkdtemp(join(tmpdir(), "attitude-atlas-"));
  try {
    try {
      await execute("ulog2csv", [
        "-m",
        "vehicle_attitude",
        "-o",
        directory,
        resolve(file),
      ]);
    } catch (e) {
      if (e.code === "ENOENT")
        throw Error(
          "ULog input requires pyulog's ulog2csv on PATH. Alternatively provide a vehicle_attitude CSV.",
        );
      throw Error("ULog conversion failed: " + (e.stderr?.trim() || e.message));
    }
    const name = basename(file).slice(0, -4) + "_vehicle_attitude_0.csv";
    try {
      return await readFile(join(directory, name), "utf8");
    } catch (e) {
      if (e.code === "ENOENT")
        throw Error("ULog has no vehicle_attitude instance 0.");
      throw e;
    }
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
}
