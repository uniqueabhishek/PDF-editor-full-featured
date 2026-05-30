"""
Ultra PDF Editor - Theme application

Shared helper for applying the light/dark Qt stylesheet, used both at startup
and when the user changes the theme in Preferences at runtime.
"""
from pathlib import Path

_STYLES_DIR = Path(__file__).parent.parent / "resources" / "styles"


def _load_stylesheet(filename: str) -> str:
    """Load a Qt stylesheet from resources/styles.

    Returns an empty string (falls back to the Fusion default) if the file is
    missing or unreadable, so a missing resource never crashes the app.
    """
    try:
        return (_STYLES_DIR / filename).read_text(encoding="utf-8")
    except OSError as e:
        print(f"Warning: could not load stylesheet '{filename}': {e}")
        return ""


def resolve_theme(theme: str) -> str:
    """Resolve a theme name to a concrete 'light' or 'dark'.

    'system' is mapped using the OS preference via darkdetect, falling back to
    'light' if that can't be determined.
    """
    if theme == "dark":
        return "dark"
    if theme == "light":
        return "light"
    try:
        import darkdetect
        return "dark" if darkdetect.isDark() else "light"
    except Exception:
        return "light"


def apply_theme(app, theme: str) -> None:
    """Apply the light/dark stylesheet for ``theme`` to the QApplication."""
    resolved = resolve_theme(theme)
    app.setStyleSheet(_load_stylesheet(f"{resolved}_theme.qss"))
