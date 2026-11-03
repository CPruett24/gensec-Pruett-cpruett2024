"""Optional UI smoke check; requires requirements.txt to be installed."""
from streamlit.testing.v1 import AppTest


initial = AppTest.from_file("app.py").run()
assert not initial.exception, initial.exception

# AppTest has no upload setter; substitute an in-memory upload at the UI boundary.
source = '''
import io
from pathlib import Path
from unittest.mock import patch
import app

upload = io.BytesIO(Path("sample.log").read_bytes())
upload.name = "sample.log"
upload.size = len(upload.getvalue())
with patch("streamlit.file_uploader", return_value=upload):
    app.main()
'''
result = AppTest.from_string(source).run()
assert not result.exception, result.exception
assert [metric.value for metric in result.metric] == ["8", "2", "6"]
assert len(result.dataframe) == 3
assert len(result.get("vega_lite_chart")) == 1
assert len(result.get("download_button")) == 1
print("Streamlit smoke checks passed: initial UI, sample metrics, tables, chart, CSV button")


def check_upload(data, filename="attack.log", declared_size=None):
    """Supply untrusted bytes as data, never as executable script fragments."""
    source = '''
import io
from unittest.mock import patch
import app
from streamlit import session_state

upload = io.BytesIO(session_state["test_data"])
upload.name = session_state["test_filename"]
upload.size = session_state["test_size"]
with patch("streamlit.file_uploader", return_value=upload):
    app.main()
'''
    check = AppTest.from_string(source)
    check.session_state["test_data"] = data
    check.session_state["test_filename"] = filename
    check.session_state["test_size"] = len(data) if declared_size is None else declared_size
    check.run()
    assert not check.exception, check.exception
    return check


for data, size, message in (
    (b"", 2 * 1024 * 1024 + 1, "limit"),
    (b"x" * (2 * 1024 * 1024 + 1), 1, "limit"),
    (b"\xff", 1, "UTF-8"),
):
    check = check_upload(data, declared_size=size)
    assert len(check.error) == 1 and message in check.error[0].value
    assert len(check.dataframe) == 0

for data in (b"", b"<script>alert(1)</script>", b"2026-11-02T10:00:00+01:60 192.0.2.1 FAILURE"):
    check = check_upload(data)
    assert not check.error
    assert [metric.value for metric in check.metric] == ["0", "0", "0"]
    assert len(check.dataframe) == 0
    assert len(check.get("download_button")) == 0

check = check_upload(b"<script>alert(1)</script>\n2026-11-02T10:00:00Z 192.0.2.1 SUCCESS", "../../outside.log")
assert [metric.value for metric in check.metric] == ["1", "1", "0"]
assert len(check.warning) == 1
assert len(check.dataframe) == 2
assert len(check.get("vega_lite_chart")) == 1
assert len(check.get("download_button")) == 1
print("Adversarial UI checks passed: size guards, invalid UTF-8, empty/malformed/HTML input, mixed valid input, path-like filename")
