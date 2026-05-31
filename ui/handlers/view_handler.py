"""
Ultra PDF Editor - View operations mixin.

Zoom, fit, rotate, view mode, sidebar and fullscreen toggles. Mixed into
MainWindow; relies on ``self._viewer``, ``self._sidebar`` and ``self._statusbar``.
"""
from typing import TYPE_CHECKING

from ..pdf_viewer import ViewMode

if TYPE_CHECKING:
    from ._context import MainWindowContext
    _MixinBase = MainWindowContext
else:
    _MixinBase = object


class ViewHandlerMixin(_MixinBase):
    """View-menu and zoom/rotation operations for MainWindow."""

    def _zoom_in(self):
        """Zoom in"""
        self._viewer.zoom_in()

    def _zoom_out(self):
        """Zoom out"""
        self._viewer.zoom_out()

    def _fit_width(self):
        """Fit to width"""
        self._viewer.fit_width()

    def _fit_page(self):
        """Fit whole page"""
        self._viewer.fit_page()

    def _rotate(self, degrees: int):
        """Rotate view"""
        self._viewer.rotate_view(degrees)

    def _set_view_mode(self, mode: ViewMode):
        """Set view mode"""
        self._viewer.set_view_mode(mode)
        self._statusbar.showMessage(f"View mode: {mode.value}", 2000)

    def _toggle_sidebar(self, visible: bool):
        """Toggle sidebar visibility"""
        self._sidebar.setVisible(visible)

    def _toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
