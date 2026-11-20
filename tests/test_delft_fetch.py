import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import zlib
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples/clock-study"))
from fetch_delft import fetch


class RangeFetchTests(unittest.TestCase):
    def test_member_name_and_integrity_before_replacing_existing_file(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("sample.ulg", b"test")
        data = buffer.getvalue()
        entry = {"path": "sample.ulg", "local_header": 0, "bytes": 4,
                 "crc32": f"{zlib.crc32(b'test'):08x}"}
        with tempfile.TemporaryDirectory() as tmp, patch("fetch_delft.read_range",
                side_effect=lambda url, n, a, k: data[a:a+k]):
            root = Path(tmp)
            source = {"archive_url": "unused", "archive_bytes": len(data)}
            fetch(root, source, entry)
            target = root / "sample.ulg"
            self.assertEqual(target.read_bytes(), b"test")
            with patch("fetch_delft.read_range", side_effect=AssertionError("downloaded a verified member")):
                fetch(root, source, entry)
            target.write_bytes(b"existing")
            with self.assertRaisesRegex(ValueError, "CRC"):
                fetch(root, source, dict(entry, crc32="00000000"))
            self.assertEqual(target.read_bytes(), b"existing")
            with self.assertRaisesRegex(ValueError, "name mismatch"):
                fetch(root, source, dict(entry, path="wrong.ulg"))
