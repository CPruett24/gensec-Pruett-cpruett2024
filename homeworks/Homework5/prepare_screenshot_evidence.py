"""Prepare static, escaped views of recorded evidence; never execute its contents."""

from hashlib import sha256
from html import escape
from pathlib import Path
import json

root = Path(__file__).resolve().parent
source = root / "test_artifacts" / "attack1_trial1.txt"
data = source.read_bytes()
lines = data.decode("utf-8-sig").splitlines()
out = root / "screenshots"
out.mkdir(exist_ok=True)

def locate(text, start=0):
    return next(i for i in range(start, len(lines)) if lines[i].startswith(text))

read_call = locate("Tool call: terminal")
write_call = locate("Tool call: terminal", read_call + 1)
payload_start = locate("--- BEGIN SYNTHETIC PROMPT-INJECTION")
payload_end = locate("--- END SYNTHETIC PROMPT-INJECTION", payload_start)
final_start = locate("Agent:")
postcheck = locate("--- INDEPENDENT POSTCHECK ---")
sections = [
    ("01_request_and_read", "Legitimate request and initial Terminal read", [(0, read_call + 2), (locate("Executing command:"), locate("Tool result:") + 1)]),
    ("02_returned_payload", "Malicious payload returned by Terminal", [(locate("Tool result:"), locate("Tool result:") + 1), (payload_start, payload_end + 1)]),
    ("03_unauthorized_write", "Additional Terminal call: marker write", [(write_call, final_start)]),
    ("04_final_response", "Final agent response and acknowledgement", [(final_start, postcheck - 1)]),
    ("05_independent_verification", "Recorded independent marker verification", [(postcheck, len(lines))]),
]
manifest = {"source": "test_artifacts/attack1_trial1.txt", "sha256": sha256(data).hexdigest(), "views": []}
for stem, title, ranges in sections:
    # Every excerpt is an exact, contiguous sequence of source lines. Gaps are labeled.
    fragments = []
    plain = []
    for start, end in ranges:
        excerpt = "\n".join(lines[start:end])
        plain.append(f"SOURCE LINES {start + 1}-{end}\n{excerpt}")
        fragments.append(f'<div class="range">Source lines {start + 1}-{end}</div><pre>{escape(excerpt)}</pre>')
    note = "Recorded transcript excerpt, rendered for evidence review. Not a live terminal screenshot or a new execution."
    html = f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>{escape(title)}</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;padding:34px 42px;background:#fff;color:#17202a;font-family:Arial,sans-serif}}
h1{{font-size:30px;margin:0 0 12px}}.note{{font-size:18px;line-height:1.4;margin-bottom:20px}}
.range{{font-size:17px;color:#38556e;margin-top:12px;font-weight:bold}}
pre{{font:22px/1.42 Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere;margin:8px 0 20px;padding:16px;background:#f3f5f7;border-left:4px solid #38556e}}
footer{{font-size:15px;line-height:1.5;overflow-wrap:anywhere;border-top:1px solid #ccc;padding-top:12px}}
@media print{{body{{padding:10mm}}pre{{font-size:12pt}}h1{{font-size:18pt}}}}
</style><h1>{escape(title)}</h1><div class="note">{note}</div>
{''.join(fragments)}<footer>Source: test_artifacts/attack1_trial1.txt<br>SHA-256: {manifest['sha256']}<br>Excerpts retain recorded text; line wrapping is for readability. Gaps are identified by source line ranges. Marker verification is historical; the marker was removed before Trial 2.</footer></html>'''
    (out / f"{stem}.html").write_text(html, encoding="utf-8")
    (out / f"{stem}.txt").write_text(note + "\n\n" + "\n\n[EXCERPT GAP]\n\n".join(plain) + "\n", encoding="utf-8")
    manifest["views"].append({"filename": stem, "source_line_ranges": [[a + 1, b] for a, b in ranges]})
(out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
(out / "README.md").write_text('''# Attack 1 screenshot evidence

These static HTML views contain excerpts of the existing Trial 1 transcript, not a rerun or a recreation of a terminal session. Text is HTML-escaped, so the payload is displayed as data. The manifest records the source hash and exact line ranges; TXT companions support manual VS Code capture.

The five numbered views cover the request/read, returned payload, unauthorized write, final response, and historical independent marker checks. PNGs, when present, are browser screenshots of these labeled evidence views. They are not original live-terminal screenshots. No timestamps or execution results were added to the excerpts.

For manual capture, open each numbered HTML file in a browser, use a window about 1400 pixels wide at 100% zoom, and use Windows Snipping Tool (Win+Shift+S) to capture the title, source ranges, and complete excerpt. Save with the same numbered filename and a .png extension. If needed, use browser full-page capture. Alternatively open its TXT companion in VS Code, enable word wrap, and capture the complete section. Do not execute the displayed commands.

At PDF inclusion, place each image on its own page, approximately page width. Check readability at 100% PDF zoom. Browser print styling also supports direct printing of HTML views to PDF. The marker verification is from Trial 1; the marker was removed before Trial 2 and must not be recreated for screenshots.
''', encoding="utf-8")
assert source.read_bytes() == data
print(f"Prepared {len(sections)} evidence views. Source SHA-256: {manifest['sha256']}")
