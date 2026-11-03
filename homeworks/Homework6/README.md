# Homework 6: Security Log Analyzer

From this directory, install and run with Python 3.12 or later:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Upload `sample.log`: expect 8 events, 2 successes, 6 failures, 1 skipped line, and 192.0.2.10 flagged with 5 failures. The app shows the top 10 IP addresses, one event-count chart, all flagged addresses, parsed events, and a CSV download.

Supported simple format: `2026-11-02T10:00:00Z 192.0.2.10 FAILURE` (SUCCESS or FAILURE, case insensitive). Timestamps require a date and seconds; use T or a space, with an optional Z or numeric timezone offset. IPv4 and IPv6 literals are supported. ISO-timestamped SSH messages follow the examples in `sample.log`. Blank lines are ignored; unsupported nonempty lines are counted and skipped.

Security controls: both the uploader and parser enforce a 2 MiB (2,097,152 byte) limit. Strict UTF-8 decoding rejects invalid bytes. Full-line matching, timestamp and IP validation, a 4,096-character line limit, and control-character rejection constrain input. Only canonical timestamp/IP/outcome fields reach tables and exports. Raw uploaded text and filenames are never rendered as HTML, evaluated, used as filesystem paths, or passed to commands. CSV fields are quoted and formula-triggering values are prefixed with an apostrophe. Uploaded content is processed in memory; the application code makes no external network requests. Streamlit serves a local browser UI; the launch command disables usage telemetry. Dependency installation requires package access.

Limitations: this intentionally narrow parser does not support yearless syslog timestamps, arbitrary vendor formats, fractional seconds, or multiline events. A missing timestamp timezone remains unspecified. Five failures is an aggregate threshold across the uploaded file, not a time-window detector or proof of an attack. File extension checks do not establish file authenticity. Uploads are not persisted; Streamlit retains data in memory during processing. Requirements constrain Streamlit to major version 1 but do not lock transitive dependencies. Keep the server local for the demonstration; authentication and production deployment are outside this homework.

Run checks from this directory:

```powershell
python -m py_compile app.py test_app.py smoke_streamlit.py
python -m unittest -v
python smoke_streamlit.py
```

Validation: syntax checks and all 12 unit tests passed. Streamlit AppTest passed for the initial screen, a simulated sample upload, and seven adversarial upload scenarios. Sample checks cover metrics, three tables, one chart, and the CSV button. The UI smoke test requires Streamlit; unit tests use only the Python standard library. The native browser file picker and actual browser download were not manually tested. Local `.streamlit/config.toml` also disables telemetry, binds to loopback, and caps uploads when launched from this directory.

Adversarial review (PROMPT 2):

| Case | Result |
| --- | --- |
| Over 2 MiB; exactly at the limit | Oversized files rejected; boundary accepted. UI tests cover both declared size and actual byte count. |
| Invalid UTF-8 | Invalid bytes, overlong encodings, truncated characters, and surrogate encodings rejected. |
| Malformed/incomplete lines | Skipped and counted; valid neighboring events preserved. |
| Invalid IPs and timestamps | Rejected. Found and fixed invalid offset minutes being normalized by Python (`+01:60` became `+02:00`). Explicit offset hour/minute ranges now reject these inputs. |
| CSV formula injection | `=`, `+`, `-`, and `@` payloads neutralized in every export column, including leading whitespace and control characters; CSV round-trip preserves one row. |
| Empty files | Empty, BOM-only, and blank files handled without errors. |
| HTML/script-like text | Unsupported lines skipped. Script-like SSH usernames are discarded; only canonical fields reach output. |
| Execution, paths, networking | Source review found no execution, file-access, or networking calls in the upload flow. Processing tests block common execution, filesystem, and socket APIs while exercising code-like payloads and path-like filenames; no calls occurred. |

Only the timezone regex required an application change. These checks cover application processing and simulated Streamlit uploads, not a formal security proof or dependency audit. Side-effect guards cover common APIs rather than every possible Python API. Spreadsheet formula defenses were checked as CSV text, not in Excel or other spreadsheet software. The aggregate failure threshold and narrow log-format limitations above remain unchanged.

For a five-minute screencast: upload `sample.log`, explain its counts and flag, run `python -m unittest -v`, run `python smoke_streamlit.py`, then show the offset validation fix and CSV escaping function.
