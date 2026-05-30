"""
Ultra PDF Editor - MainWindow handler mixins.

The MainWindow used to be a single ~1,900 line class. Its behaviour is split
here into cohesive mixin classes grouped by menu/concern. Each mixin operates on
the same MainWindow instance (shared ``self._document``, ``self._viewer``,
``self._statusbar`` ...), so method bodies are unchanged - they are simply
relocated. MainWindow inherits every mixin, so all ``self`` references continue
to resolve through the normal method-resolution order.
"""
from .file_handler import FileHandlerMixin
from .edit_handler import EditHandlerMixin
from .view_handler import ViewHandlerMixin
from .page_handler import PageHandlerMixin
from .tools_handler import ToolsHandlerMixin
from .annotation_handler import AnnotationHandlerMixin

__all__ = [
    "FileHandlerMixin",
    "EditHandlerMixin",
    "ViewHandlerMixin",
    "PageHandlerMixin",
    "ToolsHandlerMixin",
    "AnnotationHandlerMixin",
]
