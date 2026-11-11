# Dialogs Module

from .batch_dialog import BatchDialog
from .clean_pdf_dialog import CleanPDFDialog
from .crop_dialog import CropDialog
from .extract_pages_dialog import ExtractPagesDialog
from .find_dialog import FindDialog, FindReplaceDialog
from .header_footer_dialog import HeaderFooterDialog
from .merge_dialog import MergeDialog
from .remove_header_footer_dialog import RemoveHeaderFooterDialog
from .settings_dialog import SettingsDialog
from .split_dialog import SplitDialog

__all__ = [
    "BatchDialog",
    "CleanPDFDialog",
    "CropDialog",
    "ExtractPagesDialog",
    "FindDialog",
    "FindReplaceDialog",
    "HeaderFooterDialog",
    "MergeDialog",
    "RemoveHeaderFooterDialog",
    "SettingsDialog",
    "SplitDialog",
]
