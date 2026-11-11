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


def _config_in(home):
    from config import AppConfig

    new = home / ".open_pdf_editor"
    return AppConfig(
        CONFIG_DIR=new,
        TEMP_DIR=new / "temp",
        AUTOSAVE_DIR=new / "autosave",
        STAMPS_DIR=new / "stamps",
    )


def test_settings_copied_from_pre_rename_folder(tmp_path):
    legacy = tmp_path / ".ultra_pdf_editor"
    (legacy / "temp").mkdir(parents=True)
    (legacy / "settings.json").write_text('{"theme": "dark"}')
    (legacy / "ultra_pdf.log").write_text("old log")

    cfg = _config_in(tmp_path)
    cfg.ensure_dirs()

    assert (cfg.CONFIG_DIR / "settings.json").read_text() == '{"theme": "dark"}'
    assert not (cfg.CONFIG_DIR / "ultra_pdf.log").exists()
    assert (legacy / "settings.json").exists()


def test_existing_folder_is_not_overwritten(tmp_path):
    (tmp_path / ".ultra_pdf_editor").mkdir()
    (tmp_path / ".ultra_pdf_editor" / "settings.json").write_text("old")
    cfg = _config_in(tmp_path)
    cfg.CONFIG_DIR.mkdir()
    (cfg.CONFIG_DIR / "settings.json").write_text("new")

    cfg.ensure_dirs()

    assert (cfg.CONFIG_DIR / "settings.json").read_text() == "new"
