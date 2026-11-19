import { mkdtemp, writeFile, link, rm, unlink } from "node:fs/promises";
import { dirname, resolve, join } from "node:path";

// Stage in the destination filesystem. An exclusive hard link publishes each
// completed file without replacing an existing report or an input recording.
export async function saveReports(reports) {
  const staged = [],
    created = [];
  try {
    for (const [filename, content] of reports) {
      const dest = resolve(filename);
      const dir = await mkdtemp(join(dirname(dest), ".attitude-atlas-"));
      const tmp = join(dir, "report");
      staged.push({ dir, tmp, dest });
      await writeFile(tmp, content);
    }
    for (const { tmp, dest } of staged) {
      await link(tmp, dest);
      created.push(dest);
    }
  } catch (error) {
    for (const dest of created) await unlink(dest);
    throw error;
  } finally {
    for (const { dir } of staged)
      await rm(dir, { recursive: true, force: true });
  }
}
