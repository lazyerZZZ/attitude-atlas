"""Fetch selected stored ZIP members from the versioned 4TU dataset via HTTP ranges."""
import argparse
import json
from pathlib import Path
import struct
from tempfile import NamedTemporaryFile
from time import sleep
from urllib.error import URLError
from urllib.request import Request, urlopen
import zlib

HERE = Path(__file__).resolve().parent
CHUNK = 4 * 1024 * 1024


def read_range(url, total, start, count):
    end = start + count - 1
    if not (0 <= start <= end < total):
        raise ValueError("Range outside the published archive")
    # Include the range in the cache key for proxies caching partial responses.
    request = Request(f"{url}?range={start}-{end}", headers={"Range": f"bytes={start}-{end}"})
    for attempt in range(4):
        try:
            with urlopen(request, timeout=75) as response:
                if response.status != 206 or response.headers.get("Content-Range") != f"bytes {start}-{end}/{total}":
                    raise ValueError("Archive server did not confirm the requested byte range")
                data = response.read(count + 1)
                if len(data) == count:
                    return data
                raise OSError("Incomplete archive range")
        except (OSError, URLError) as error:
            if attempt == 3:
                raise
            sleep(2 ** attempt)


def fetch(root, source, entry):
    path = root / entry["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    header = entry["local_header"]
    def read(start, count):
        return read_range(source["archive_url"], source["archive_bytes"], start, count)
    raw = read(header, 30)
    if raw[:4] != b"PK\x03\x04" or struct.unpack_from("<H", raw, 8)[0] != 0:
        raise ValueError("Expected a stored ZIP member")
    name_size, extra_size = struct.unpack_from("<HH", raw, 26)
    if read(header + 30, name_size).decode("utf-8") != entry["path"]:
        raise ValueError("Archive member name mismatch")
    start = header + 30 + name_size + extra_size
    crc = 0
    with NamedTemporaryFile(dir=path.parent, delete=False) as out:
        partial = Path(out.name)
    try:
        with partial.open("wb") as out:
            for offset in range(0, entry["bytes"], CHUNK):
                data = read(start + offset, min(CHUNK, entry["bytes"] - offset))
                crc = zlib.crc32(data, crc)
                out.write(data)
        if f"{crc:08x}" != entry["crc32"]:
            raise ValueError("Archive member CRC mismatch")
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)


if __name__ == "__main__":
    manifest = json.loads((HERE / "delft-sources.json").read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--case", choices=manifest["captures"])
    args = parser.parse_args()
    for code, files in manifest["captures"].items():
        if args.case is None or code == args.case:
            for entry in files.values():
                fetch(args.directory, manifest, entry)
