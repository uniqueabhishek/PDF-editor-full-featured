"""
Open PDF Editor - Theme application

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
    except Exception:  # noqa: BLE001 - OS theme detection is optional; fall back to light
        return "light"


_current = "light"


def current_theme() -> str:
    """The resolved theme last applied: 'light' or 'dark'.

    Drawn icons ask this which colour to use.
    """
    return _current


# Colours for every palette role the widgets fall back on. The stylesheets only
# style some widgets; anything they leave out (labels, check boxes, menu text in
# the light theme, dialogs) takes its colours from the palette. Left to the OS,
# that palette is dark whenever Windows is in dark mode, which put white text on
# the light theme's white backgrounds.
_PALETTES = {
    "light": {
        "Window": "#f5f5f5",
        "WindowText": "#1e1e1e",
        "Base": "#ffffff",
        "AlternateBase": "#f0f0f0",
        "Text": "#1e1e1e",
        "Button": "#f0f0f0",
        "ButtonText": "#1e1e1e",
        "BrightText": "#d13438",
        "ToolTipBase": "#ffffff",
        "ToolTipText": "#1e1e1e",
        "Highlight": "#0078d4",
        "HighlightedText": "#ffffff",
        "Link": "#0067c0",
        "PlaceholderText": "#808080",
        "disabled": "#a0a0a0",
    },
    "dark": {
        "Window": "#2d2d2d",
        "WindowText": "#ffffff",
        "Base": "#252525",
        "AlternateBase": "#2d2d2d",
        "Text": "#ffffff",
        "Button": "#3d3d3d",
        "ButtonText": "#ffffff",
        "BrightText": "#ff6b6b",
        "ToolTipBase": "#3d3d3d",
        "ToolTipText": "#ffffff",
        "Highlight": "#0078d4",
        "HighlightedText": "#ffffff",
        "Link": "#4ea3ff",
        "PlaceholderText": "#9a9a9a",
        "disabled": "#7a7a7a",
    },
}


def _build_palette(theme: str):
    from PyQt6.QtGui import QColor, QPalette

    colours = _PALETTES[theme]
    palette = QPalette()
    for role_name, value in colours.items():
        if role_name != "disabled":
            palette.setColor(getattr(QPalette.ColorRole, role_name), QColor(value))
    disabled = QColor(colours["disabled"])
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, disabled)
    return palette


def apply_theme(app, theme: str) -> None:
    """Apply the light/dark palette and stylesheet for ``theme`` to the QApplication."""
    global _current  # noqa: PLW0603 - one app-wide theme, read by current_theme()
    resolved = resolve_theme(theme)
    _current = resolved

    # Tell Qt the scheme too (Qt 6.8+), so the window title bar matches.
    from PyQt6.QtCore import Qt

    hints = app.styleHints()
    if hasattr(hints, "setColorScheme"):
        hints.setColorScheme(Qt.ColorScheme.Dark if resolved == "dark" else Qt.ColorScheme.Light)

    app.setPalette(_build_palette(resolved))
    app.setStyleSheet(_load_stylesheet(f"{resolved}_theme.qss"))
