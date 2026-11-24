"""The OPEN_PDF_SMOKE_TEST start-up mode used to check packaged builds."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run(pdf: Path, home: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(
        OPEN_PDF_SMOKE_TEST=str(pdf),
        QT_QPA_PLATFORM="offscreen",
        OPEN_PDF_RENDER_IN_PROCESS="0",  # exercise the real render process
        USERPROFILE=str(home),
        HOME=str(home),
    )
    return subprocess.run(
        [sys.executable, str(ROOT / "Open_PDF_Editor.py")],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,  # the exit code is what the tests check
    )


def _log(home: Path) -> str:
    return (home / ".open_pdf_editor" / "open_pdf_editor.log").read_text(encoding="utf-8")


def test_smoke_mode_renders_and_exits_cleanly(tmp_path, make_pdf):
    pdf = make_pdf("smoke.pdf", pages=3)
    result = _run(pdf, tmp_path / "home")
    assert result.returncode == 0, result.stderr
    assert "SMOKE OK 3 pages" in _log(tmp_path / "home")


def test_smoke_mode_fails_on_a_file_it_cannot_open(tmp_path):
    bad = tmp_path / "broken.pdf"
    bad.write_bytes(b"not a pdf")
    result = _run(bad, tmp_path / "home")
    assert result.returncode != 0
    assert "SMOKE FAILED" in _log(tmp_path / "home")
