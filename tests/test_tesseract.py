"""Locating the Tesseract engine."""

from utils import tesseract


def test_tesseract_cmd_setting_wins(tmp_path, monkeypatch):
    exe = tmp_path / "tesseract.exe"
    exe.write_bytes(b"")
    monkeypatch.setenv("TESSERACT_CMD", f'"{exe}"')
    assert tesseract._locate() == str(exe)


def test_missing_tesseract_cmd_falls_back_to_search(tmp_path, monkeypatch):
    monkeypatch.setenv("TESSERACT_CMD", str(tmp_path / "missing.exe"))
    monkeypatch.setattr(tesseract.shutil, "which", lambda _name: "C:/found/tesseract.exe")
    assert tesseract._locate() == "C:/found/tesseract.exe"
