"""Download only the pinned files needed to reproduce the transfer evaluation."""
import argparse
import json
from pathlib import Path
import os
import subprocess
from tempfile import NamedTemporaryFile
from urllib.parse import quote

from reproduce import HERE, verified_file


def fetch(root, spec, entry):
    path = root / entry["path"]
    if path.exists():
        verified_file(root, entry)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    base = ("https://media.githubusercontent.com/media" if entry.get("lfs")
            else "https://raw.githubusercontent.com")
    url = f"{base}/{spec['repository']}/{spec['revision']}/{quote(entry['path'])}"
    with NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        tmp = Path(handle.name)
    try:
        subprocess.run(["curl", "-fsSL", "--retry", "4", "--retry-all-errors",
                        "--connect-timeout", "15", "--max-time", "300", url, "-o", str(tmp)], check=True)
        verified_file(tmp.parent, {"path": tmp.name, "sha256": entry["sha256"]})
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    specs = json.loads((HERE / "holdout-sources.json").read_text())
    original = json.loads((HERE / "sources.json").read_text())
    original["captures"] = {"ground_effect": original["captures"]["ground_effect"]}
    specs["original"] = original
    for group, spec in specs.items():
        for files in spec["captures"].values():
            for entry in files.values():
                fetch(args.root / group, spec, entry)
