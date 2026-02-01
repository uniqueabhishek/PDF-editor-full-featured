# Ultra PDF Editor - Broken/Stub Features Report

**Report Date**: 2026-02-01
**Version Analyzed**: 1.0.0

---

## Executive Summary

This report identifies features that appear in the Ultra PDF Editor UI (menus, toolbars) but are **not actually implemented** or have only **stub/placeholder implementations**. These features appear to work from a user's perspective (menu items are clickable, shortcuts work) but do nothing or show "not implemented" messages.

### Impact Summary

| Category | Total Features | Implemented | Stub/Broken | Partial |
|----------|---------------|-------------|-------------|---------|
| File Operations | 10 | 8 | 2 | 0 |
| Edit Operations | 9 | 1 | 8 | 0 |
| View Operations | 8 | 6 | 2 | 0 |
| Page Operations | 7 | 5 | 2 | 0 |
| Tools | 10 | 4 | 5 | 1 |
| Annotations | 12 | 0 | 0 | 12 |
| **TOTAL** | **56** | **24** | **19** | **13** |

---

## Critical Stub Features (Do Nothing)

### 1. Edit Menu - Complete Stub Functions

| Feature | Menu Location | Shortcut | Implementation Status | File:Line |
|---------|--------------|----------|----------------------|-----------|
| **Undo** | Edit → Undo | Ctrl+Z | `pass` - does nothing | [main_window.py:556-558](../ui/main_window.py#L556-L558) |
| **Redo** | Edit → Redo | Ctrl+Y | `pass` - does nothing | [main_window.py:560-562](../ui/main_window.py#L560-L562) |
| **Cut** | Edit → Cut | Ctrl+X | `pass` - does nothing | [main_window.py:564-566](../ui/main_window.py#L564-L566) |
| **Copy** | Edit → Copy | Ctrl+C | `pass` - does nothing | [main_window.py:568-570](../ui/main_window.py#L568-L570) |
| **Paste** | Edit → Paste | Ctrl+V | `pass` - does nothing | [main_window.py:572-574](../ui/main_window.py#L572-L574) |
| **Delete** | Edit → Delete | Delete | `pass` - does nothing | [main_window.py:576-578](../ui/main_window.py#L576-L578) |
| **Select All** | Edit → Select All | Ctrl+A | `pass` - does nothing | [main_window.py:580-582](../ui/main_window.py#L580-L582) |
| **Find** | Edit → Find | Ctrl+F | `pass` - does nothing | [main_window.py:584-586](../ui/main_window.py#L584-L586) |
| **Find & Replace** | Edit → Find & Replace | Ctrl+H | `pass` - does nothing | [main_window.py:588-590](../ui/main_window.py#L588-L590) |

**Note**: The toolbar search box (`_search` method at line 592-604) does work for basic text search, but the menu's Find/Replace dialogs are not implemented.

---

### 2. View Menu - Stub Functions

| Feature | Menu Location | Implementation Status | File:Line |
|---------|--------------|----------------------|-----------|
| **View Mode (Single/Two/Continuous)** | View → View Mode | `pass` - does nothing | [main_window.py:628-630](../ui/main_window.py#L628-L630) |

**Note**: Although `_set_view_mode()` is a stub, the `ViewMode` enum exists and the viewer has `_view_mode` property, but changing it has no visual effect.

---

### 3. Page Menu - Stub Functions

| Feature | Menu Location | Implementation Status | File:Line |
|---------|--------------|----------------------|-----------|
| **Extract Pages Dialog** | Page → Extract Pages | `pass` - does nothing | [main_window.py:706-708](../ui/main_window.py#L706-L708) |
| **Crop Page** | Page → Crop Page | `pass` - does nothing | [main_window.py:722-724](../ui/main_window.py#L722-L724) |

**Note**: `_extract_specific_pages()` at line 710-720 works when called from sidebar context menu, but the menu item does nothing.

---

### 4. Tools Menu - Stub/Message-Only Functions

| Feature | Menu Location | Implementation Status | File:Line |
|---------|--------------|----------------------|-----------|
| **OCR** | Tools → OCR | Shows "not yet implemented" message | [main_window.py:785-787](../ui/main_window.py#L785-L787) |
| **Add Header/Footer** | Tools → Add Header/Footer | `pass` - does nothing | [main_window.py:801-803](../ui/main_window.py#L801-L803) |
| **Remove Password** | Tools → Remove Password | `pass` - does nothing | [main_window.py:818-820](../ui/main_window.py#L818-L820) |
| **Batch Process** | Tools → Batch Process | `pass` - does nothing | [main_window.py:822-824](../ui/main_window.py#L822-L824) |

---

### 5. File Menu - Message-Only Functions

| Feature | Menu Location | Implementation Status | File:Line |
|---------|--------------|----------------------|-----------|
| **Print** | File → Print | Shows "not yet implemented" message | [main_window.py:526-531](../ui/main_window.py#L526-L531) |
| **Export as Word** | File → Export → Word | Shows "not yet implemented" message | [main_window.py:845-847](../ui/main_window.py#L845-L847) |

---

## Partially Implemented Features

### 6. Annotation Tools (UI Present, Backend Ready, Not Connected)

The annotation toolbar has tools for all these features, and the backend classes exist in [annotations/base.py](../annotations/base.py), but they are **NOT connected** to the viewer:

| Tool | Toolbar Button | Backend Class | Connection Status |
|------|---------------|---------------|-------------------|
| Highlight | ✅ Present | `TextMarkupAnnotation` | ❌ Not connected |
| Underline | ✅ Present | `TextMarkupAnnotation` | ❌ Not connected |
| Strikethrough | ✅ Present | `TextMarkupAnnotation` | ❌ Not connected |
| Sticky Note | ✅ Present | `TextAnnotation` | ❌ Not connected |
| Text Box | ✅ Present | `FreeTextAnnotation` | ❌ Not connected |
| Rectangle | ✅ Present | `ShapeAnnotation` | ❌ Not connected |
| Circle | ✅ Present | `ShapeAnnotation` | ❌ Not connected |
| Line | ✅ Present | `ShapeAnnotation` | ❌ Not connected |
| Arrow | ✅ Present | `ShapeAnnotation` | ❌ Not connected |
| Freehand | ✅ Present | `InkAnnotation` | ❌ Not connected |
| Eraser | ✅ Present | N/A | ❌ Not implemented |
| Redaction | ✅ Present | `RedactionAnnotation` | ❌ Not connected |

**Issue**: The `PDFViewer` sets tool modes via `set_tool_mode()` but `_on_annotation_created()` only handles `SELECT` mode:

```python
# pdf_viewer.py:387-391
def _on_annotation_created(self, page_num: int, annot_type: str, rect: QRectF):
    """Handle annotation creation"""
    if self._tool_mode == ToolMode.SELECT:
        self.selection_changed.emit(page_num, rect)
    # Other modes are NOT handled!
```

---

### 7. Form Handling (Backend Ready, No UI)

The form field classes in [forms/form_field.py](../forms/form_field.py) are fully implemented:

- `TextField`, `CheckboxField`, `RadioField`, `DropdownField`, `ListboxField`, `ButtonField`, `SignatureField`
- `FormManager` class for loading/saving forms

**Issue**: There is **no UI for creating forms**. No "Forms" menu exists. Users cannot:
- Create fillable forms
- Fill existing forms (though they render)
- Export/import form data

---

### 8. Dialogs - Created But Not Used

Custom dialogs exist but main_window uses inline `QFileDialog` instead:

| Dialog | File | Used in MainWindow? |
|--------|------|---------------------|
| `MergeDialog` | [ui/dialogs/merge_dialog.py](../ui/dialogs/merge_dialog.py) | ❌ No - uses inline code |
| `SplitDialog` | [ui/dialogs/split_dialog.py](../ui/dialogs/split_dialog.py) | ❌ No - uses inline code |
| `SettingsDialog` | [ui/dialogs/settings_dialog.py](../ui/dialogs/settings_dialog.py) | ❌ No settings menu |

---

### 9. Sidebar Issues

| Feature | Status | Issue |
|---------|--------|-------|
| Bookmark Add | Partial | Dialog shown but not saved to document |
| Bookmark Rename | Partial | UI updates but document not modified |
| Bookmark Delete | Partial | Removed from UI but not from document TOC |
| Page Reorder (Drag & Drop) | Not Working | Signal exists but not connected |

See [sidebar.py:400-424](../ui/sidebar.py#L400-L424) - bookmark operations update UI but don't call document methods.

---

### 10. PDF Viewer - Not Fully Implemented

| Feature | Status | Issue |
|---------|--------|-------|
| `get_selected_text()` | Stub | Returns empty string - [pdf_viewer.py:494-497](../ui/pdf_viewer.py#L494-L497) |
| Text selection | Partial | Selection rect drawn but text not extracted |
| Annotation rendering | Not Working | Annotations not rendered on page pixmaps |

---

## Backend Ready but No UI

These backend features are implemented in `core/pdf_document.py` but have no menu/toolbar access:

| Feature | Backend Method | UI Access |
|---------|---------------|-----------|
| Add bookmark | `add_bookmark()` | None |
| Set/Get TOC | `set_toc()`, `get_toc()` | None (sidebar shows but can't edit) |
| Add text to page | `add_text()` | None |
| Insert image | `insert_image()` | None |
| Extract all images | `extract_all_images()` | None |
| Split by ranges | `split_by_ranges()` | None |
| Image watermark | `add_image_watermark()` | None |
| Set metadata | `set_metadata()` | None (can only view properties) |

---

## Converters - Not Implemented

Files exist but contain placeholder implementations:

| Converter | File | Status |
|-----------|------|--------|
| PDF to Word | `core/converters/to_word.py` | Needs `python-docx` integration |
| PDF to Excel | `core/converters/to_excel.py` | Needs `openpyxl` integration |
| PDF to Image | `core/converters/to_image.py` | Works via `render_page_to_image()` |

---

## OCR - Backend Exists, Not Connected

| File | Status |
|------|--------|
| `core/operations/ocr.py` | Class exists with `OCRProcessor` but not connected to menu |

The OCR menu item just shows a message instead of calling the processor.

---

## Recommendations for Implementation Priority

### High Priority (Core User Experience)
1. **Find/Find & Replace** - Essential editing feature
2. **Undo/Redo** - Requires command pattern implementation
3. **Connect Annotations** - Backend ready, needs UI wiring
4. **OCR Integration** - Backend ready, needs UI connection

### Medium Priority (Professional Features)
5. **Print functionality**
6. **Export to Word** - Requires python-docx
7. **Form creation UI**
8. **Batch processing dialog**

### Lower Priority (Nice to Have)
9. **View modes** (Single/Two page/Continuous)
10. **Page cropping**
11. **Header/Footer**
12. **Password removal**

---

## Code Quality Notes

1. **Stub Pattern**: Many methods use bare `pass`:
   ```python
   def _undo(self):
       """Undo last action"""
       pass  # No implementation
   ```

2. **Message Pattern**: Some show user feedback but do nothing:
   ```python
   def _run_ocr(self):
       self._statusbar.showMessage("OCR not yet implemented", 3000)
   ```

3. **Missing Connections**: Backend classes exist but UI doesn't use them:
   - `annotations/base.py` - Full annotation system
   - `forms/form_field.py` - Full form system
   - `ui/dialogs/` - Custom dialogs

---

## Summary

**19 features** appear in the UI but do nothing or show "not implemented" messages.

**13 features** are partially implemented (backend ready, UI missing or not connected).

**Critical User Impact**: Basic editing operations (Undo, Cut, Copy, Paste, Find) do not work, which is unexpected for any editor application.

---

*Report generated for Ultra PDF Editor v1.0.0*
