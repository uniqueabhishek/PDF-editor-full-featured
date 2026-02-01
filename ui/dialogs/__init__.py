# Dialogs Module

from .merge_dialog import MergeDialog
from .split_dialog import SplitDialog
from .settings_dialog import SettingsDialog
from .find_dialog import FindDialog, FindReplaceDialog
from .extract_pages_dialog import ExtractPagesDialog
from .crop_dialog import CropDialog
from .header_footer_dialog import HeaderFooterDialog
from .batch_dialog import BatchDialog

__all__ = [
    'MergeDialog',
    'SplitDialog',
    'SettingsDialog',
    'FindDialog',
    'FindReplaceDialog',
    'ExtractPagesDialog',
    'CropDialog',
    'HeaderFooterDialog',
    'BatchDialog',
]
