"""Tests for UserSettings persistence and recent-files handling (headless)."""
from config import UserSettings


def test_settings_round_trip(tmp_path):
    s = UserSettings()
    s.theme = "dark"
    s.zoom_level = 150.0
    s.recent_files = [r"C:\docs\a.pdf"]
    path = tmp_path / "settings.json"
    s.save(path)

    loaded = UserSettings.load(path)
    assert loaded.theme == "dark"
    assert loaded.zoom_level == 150.0
    assert loaded.recent_files == [r"C:\docs\a.pdf"]


def test_load_missing_returns_defaults(tmp_path):
    loaded = UserSettings.load(tmp_path / "absent.json")
    assert loaded.theme == "system"
    assert loaded.recent_files == []


def test_load_corrupt_json_returns_defaults(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{ this is not valid json", encoding="utf-8")
    loaded = UserSettings.load(path)
    assert isinstance(loaded, UserSettings)
    assert loaded.theme == "system"


def test_load_ignores_unknown_keys(tmp_path):
    path = tmp_path / "extra.json"
    path.write_text('{"theme": "light", "bogus_key": 123}', encoding="utf-8")
    loaded = UserSettings.load(path)
    assert loaded.theme == "light"
    assert not hasattr(loaded, "bogus_key")


def test_add_recent_file_dedups_and_moves_to_front():
    s = UserSettings()
    s.add_recent_file("a.pdf")
    s.add_recent_file("b.pdf")
    s.add_recent_file("a.pdf")  # re-adding moves it to the front
    assert len(s.recent_files) == 2
    assert s.recent_files[0].endswith("a.pdf")


def test_add_recent_file_respects_limit():
    s = UserSettings()
    for i in range(30):
        s.add_recent_file(f"file_{i}.pdf", max_files=5)
    assert len(s.recent_files) == 5


def test_clear_recent_files():
    s = UserSettings()
    s.add_recent_file("a.pdf")
    s.clear_recent_files()
    assert s.recent_files == []
