import json
import subprocess
import sys


def test_dump_openapi_writes_valid_spec(tmp_path, monkeypatch):
    out = tmp_path / "openapi.json"
    monkeypatch.setenv("OPENAPI_OUT", str(out))
    result = subprocess.run(
        [sys.executable, "scripts/dump_openapi.py"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    spec = json.loads(out.read_text())
    assert spec["openapi"].startswith("3.")
    assert spec["info"]["title"] == "SimSwarm"
    paths = " ".join(spec["paths"].keys())
    assert "/api/auth" in paths
    assert "/api/jobs" in paths
