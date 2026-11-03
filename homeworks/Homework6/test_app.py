import csv
import io
from pathlib import Path
import unittest
from unittest.mock import patch

from app import FIELDS, MAX_BYTES, export_csv, parse_upload, summarize


class AnalyzerTests(unittest.TestCase):
    def test_sample_and_threshold(self):
        events, skipped = parse_upload(Path(__file__).with_name("sample.log").read_bytes(), "sample.log")
        self.assertEqual((len(events), skipped), (8, 1))
        self.assertEqual(sum(e["outcome"] == "success" for e in events), 2)
        self.assertEqual([r["ip_address"] for r in summarize(events) if r["failed_logins"] >= 5], ["192.0.2.10"])
        self.assertEqual(len(list(csv.DictReader(io.StringIO(export_csv(events).decode())))), 8)

    def test_upload_validation(self):
        for data, name in [(b"x" * (MAX_BYTES + 1), "x.log"), (b"\xff", "x.txt"), (b"", "x.py")]:
            with self.subTest(name=name, size=len(data)), self.assertRaises(ValueError):
                parse_upload(data, name)
        self.assertEqual(parse_upload(b" " * MAX_BYTES, "x.LOG"), ([], 0))
        self.assertEqual(parse_upload(b"", "x.txt"), ([], 0))

    def test_malformed_and_unsafe_lines(self):
        lines = ["2026-02-30T10:00:00Z 192.0.2.1 SUCCESS", "2026-11-02T10:00:00Z 999.1.1.1 FAILURE", "2026-11-02T10:00:00Z 192.0.2.1 SUCCESS <script>alert(1)</script>", "__import__('os').system('echo unsafe')", "x" * 4097, "2026-11-02T10:00:00Z fe80::1%eth0 SUCCESS", "2026-11-02T10:00:00Z\t192.0.2.1 SUCCESS"]
        self.assertEqual(parse_upload("\n".join(lines).encode(), "x.log"), ([], len(lines)))

    def test_bom_ipv6_and_timestamp(self):
        events, skipped = parse_upload("\ufeff2026-11-02 10:00:00+02:00 2001:0db8::1 success".encode(), "x.txt")
        self.assertEqual(skipped, 0)
        self.assertEqual(events[0]["ip_address"], "2001:db8::1")
        self.assertEqual(events[0]["timestamp"], "2026-11-02T10:00:00+02:00")

    def test_csv_formula_injection(self):
        for payload in ("=1+1", "+cmd", "-1+2", "@SUM(A1)", "  =1+1", "\t=1", "\r=1", "\n=1"):
            with self.subTest(payload=payload):
                exported = export_csv([dict(timestamp=payload, ip_address="192.0.2.1", outcome="success")])
                row = next(csv.DictReader(io.StringIO(exported.decode())))
                self.assertEqual(row["timestamp"], "'" + payload)

    def test_invalid_timestamps_and_addresses(self):
        for timestamp in ("2026-02-30T10:00:00Z", "0000-01-01T10:00:00Z", "2026-11-02T24:00:00Z", "2026-11-02T10:60:00Z", "2026-11-02T10:00:60Z", "2026-11-02T10:00:00+01:60", "2026-11-02T10:00:00-00:99", "2026-11-02T10:00:00+24:00"):
            with self.subTest(timestamp=timestamp):
                self.assertEqual(parse_upload(f"{timestamp} 192.0.2.1 SUCCESS".encode(), "x.log"), ([], 1))
        for address in ("999.1.1.1", "192.0.2", "192.0.2.01", "example.com", "2001:db8:::1", "fe80::1%eth0", "=1+1"):
            with self.subTest(address=address):
                self.assertEqual(parse_upload(f"2026-11-02T10:00:00Z {address} FAILURE".encode(), "x.log"), ([], 1))

    def test_incomplete_and_mixed_lines(self):
        invalid = ["2026-11-02", "2026-11-02T10:00:00Z", "2026-11-02T10:00:00Z 192.0.2.1", "192.0.2.1 SUCCESS", "2026-11-02T10:00:00Z 192.0.2.1 UNKNOWN"]
        valid = "2026-11-02T10:00:00Z 192.0.2.1 SUCCESS"
        events, skipped = parse_upload("\n".join(invalid + [valid]).encode(), "x.log")
        self.assertEqual((len(events), skipped), (1, len(invalid)))

    def test_utf8_variants_and_empty_files(self):
        for data in (b"\xff", b"\xc0\xaf", b"\xe2\x82", b"\xed\xa0\x80"):
            with self.subTest(data=data), self.assertRaisesRegex(ValueError, "UTF-8"):
                parse_upload(data, "x.log")
        for data in (b"", b"\xef\xbb\xbf", b" \r\n\n"):
            self.assertEqual(parse_upload(data, "x.txt"), ([], 0))
        self.assertEqual(export_csv([]).decode(), '"timestamp","ip_address","outcome"\r\n')

    def test_size_boundary(self):
        for size in (MAX_BYTES + 1, MAX_BYTES * 2):
            with self.subTest(size=size), self.assertRaisesRegex(ValueError, "limit"):
                parse_upload(b"x" * size, "x.log")
        self.assertEqual(parse_upload(b" " * MAX_BYTES, "x.log"), ([], 0))

    def test_formula_protection_in_every_export_column(self):
        for field in FIELDS:
            for payload in ('=HYPERLINK("https://example.invalid")', "+1+1", "-1+1", "@SUM(A1)", "  =1", "\t+1", "\r-1", "\n@SUM(A1)"):
                with self.subTest(field=field, payload=payload):
                    event = dict(timestamp="2026-11-02T10:00:00", ip_address="192.0.2.1", outcome="success")
                    event[field] = payload
                    rows = list(csv.DictReader(io.StringIO(export_csv([event]).decode(), newline="")))
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(rows[0][field], "'" + payload)

    def test_html_is_rejected_or_discarded(self):
        script = "<script>alert(1)</script>"
        raw = f"2026-11-02T10:00:00Z 192.0.2.1 SUCCESS {script}\n2026-11-02T10:00:00Z host sshd[1]: Accepted password for {script} from 192.0.2.1 port 123 ssh2"
        events, skipped = parse_upload(raw.encode(), "x.log")
        self.assertEqual((len(events), skipped), (1, 1))
        self.assertNotIn("<script>", export_csv(events).decode())

    def test_upload_has_no_execution_filesystem_or_network_side_effects(self):
        # Patches are active only during application processing, not fixture reads.
        payload = b"__import__('os').system('echo unsafe')\n2026-11-02T10:00:00Z 192.0.2.1 SUCCESS"
        with patch("builtins.open", side_effect=AssertionError("filesystem access")), patch("pathlib.Path.open", side_effect=AssertionError("path access")), patch("os.open", side_effect=AssertionError("filesystem access")), patch("os.system", side_effect=AssertionError("command execution")), patch("subprocess.Popen", side_effect=AssertionError("process execution")), patch("builtins.eval", side_effect=AssertionError("eval")), patch("builtins.exec", side_effect=AssertionError("exec")), patch("socket.socket", side_effect=AssertionError("network access")):
            for filename in ("../../outside.log", "C:\\outside\\attack.log", "<script>evil</script>.log"):
                events, skipped = parse_upload(payload, filename)
                self.assertEqual((len(events), skipped), (1, 1))
                self.assertEqual(len(summarize(events)), 1)
                self.assertIn(b"192.0.2.1", export_csv(events))


if __name__ == "__main__":
    unittest.main()
