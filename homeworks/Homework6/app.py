"""Small, offline authentication log analyzer. Run: streamlit run app.py."""

import csv
from datetime import datetime
import io
import ipaddress
import re

MAX_BYTES = 2 * 1024 * 1024
MAX_LINE_LENGTH = 4096
FIELDS = ["timestamp", "ip_address", "outcome"]
# Supported timestamps are ISO dates with seconds and an optional UTC offset.
# Check offset ranges explicitly: fromisoformat normalizes offsets like +01:60.
TIMESTAMP = r"(?P<timestamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)?)"
SIMPLE = re.compile(TIMESTAMP + r"\s+(?P<ip>\S+)\s+(?P<outcome>SUCCESS|FAILURE)\s*", re.I)
SSH = re.compile(
    TIMESTAMP + r"\s+[\w.-]+\s+sshd\[\d+\]:\s+"
    r"(?P<outcome>Accepted|Failed) (?:password|publickey) for "
    r"(?:invalid user )?\S+ from (?P<ip>\S+) port \d+ ssh2\s*"
)


def parse_upload(data: bytes, filename: str):
    """Validate bytes and return canonical events plus a skipped-line count."""
    if not filename.lower().endswith((".log", ".txt")):
        raise ValueError("Choose a .log or .txt file.")
    if len(data) > MAX_BYTES:
        raise ValueError("File exceeds the 2 MB (2,097,152 byte) limit.")
    try:
        content = data.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("File must contain valid UTF-8 text.") from exc
    events = []
    skipped = 0
    for line in content.splitlines():
        if not line.strip():
            continue
        if len(line) > MAX_LINE_LENGTH or any(ord(c) < 32 for c in line):
            skipped += 1
            continue
        match = SIMPLE.fullmatch(line) or SSH.fullmatch(line)
        if not match:
            skipped += 1
            continue
        try:
            timestamp = datetime.fromisoformat(match["timestamp"].replace("Z", "+00:00"))
            # Reject IPv6 scope IDs; accept only literal IPv4/IPv6 addresses.
            if "%" in match["ip"]:
                raise ValueError("Scoped addresses are unsupported")
            address = str(ipaddress.ip_address(match["ip"]))
        except ValueError:
            skipped += 1
            continue
        outcome = "success" if match["outcome"].lower() in ("success", "accepted") else "failure"
        events.append(dict(zip(FIELDS, (timestamp.isoformat(), address, outcome))))
    return events, skipped


def summarize(events):
    counts = {}
    for event in events:
        row = counts.setdefault(event["ip_address"], {"ip_address": event["ip_address"], "total_events": 0, "failed_logins": 0})
        row["total_events"] += 1
        row["failed_logins"] += event["outcome"] == "failure"
    return sorted(counts.values(), key=lambda row: (-row["total_events"], row["ip_address"]))


def csv_cell(value):
    """Neutralize spreadsheet formulas, including leading whitespace tricks."""
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


def export_csv(events):
    output = io.StringIO(newline="")
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    writer.writerow(FIELDS)
    for event in events:
        writer.writerow([csv_cell(event[field]) for field in FIELDS])
    return output.getvalue().encode("utf-8")


def main():
    import streamlit as st

    st.set_page_config(page_title="Security Log Analyzer", layout="wide")
    st.title("Security Log Analyzer")
    st.write("Upload a UTF-8 .log or .txt file (maximum 2 MB). Processing stays in this application; uploaded content is never executed or saved.")
    st.caption("Format: 2026-11-02T10:00:00Z 192.0.2.10 FAILURE. ISO-timestamped SSH Accepted/Failed password or publickey messages are also supported.")
    upload = st.file_uploader("Authentication log", type=["log", "txt"], max_upload_size=2)
    if upload is None:
        return
    if upload.size > MAX_BYTES:
        st.error("File exceeds the 2 MB (2,097,152 byte) limit.")
        return
    try:
        events, skipped = parse_upload(upload.read(MAX_BYTES + 1), upload.name)
    except ValueError as exc:
        st.error(str(exc))
        return
    if skipped:
        st.warning(f"Skipped {skipped} malformed or unsupported nonempty lines.")
    failures = sum(event["outcome"] == "failure" for event in events)
    columns = st.columns(3)
    for column, label, value in zip(columns, ("Total events", "Successful logins", "Failed logins"), (len(events), len(events) - failures, failures)):
        column.metric(label, value)
    if not events:
        st.info("No supported authentication events found.")
        return
    addresses = summarize(events)
    st.subheader("Most frequent IP addresses")
    st.dataframe(addresses[:10], hide_index=True)
    st.bar_chart({"IP address": [row["ip_address"] for row in addresses[:10]], "Events": [row["total_events"] for row in addresses[:10]]}, x="IP address", y="Events")
    st.subheader("Flagged IP addresses: 5 or more failed logins")
    flagged = [row for row in addresses if row["failed_logins"] >= 5]
    if flagged:
        st.dataframe(flagged, hide_index=True)
    else:
        st.info("No IP addresses meet the threshold.")
    st.subheader("Parsed events")
    st.dataframe(events, hide_index=True)
    st.download_button("Download parsed events as CSV", export_csv(events), file_name="parsed_events.csv", mime="text/csv")


if __name__ == "__main__":
    main()
