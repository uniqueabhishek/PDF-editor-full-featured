# Ultra PDF Editor — Audit Remediation To-Do

Living checklist derived from the code audit of the v1.0.0 tree.
**Last updated:** 2026-05-31.

This is the authoritative status list. The older `CODE_QUALITY_REPORT.md`,
`docs/BROKEN_FEATURES_REPORT.md` and `docs/FEATURE_AUDIT_REPORT.md` are stale and
contradict each other and the code (see item #10).

---

## ✅ Done

- [x] **#1 — Encryption was a no-op (critical / security).** `encrypt()` never
  applied encryption and a same-file save did an incremental `PDF_ENCRYPT_KEEP`,
  so "Encrypt PDF" produced an *unencrypted* file. Now queues AES-256 settings
  applied via a full rewrite, with password confirmation in the UI.
  — commit `aa0f28b`
- [x] **#2 — Undo of "Delete Page" destroyed content.** `PageDeleteCommand.undo()`
  inserted a blank page. Now snapshots the page and restores the real content.
  — commit `0ab2380`
- [x] **#3 — Destructive ops bypassed undo / were irreversible.** Redaction, crop,
  header/footer, OCR and watermark are now undoable via `DocumentSnapshotCommand`.
  — commit `8f4974e`
- [x] **#4 — Render-thread safety.** `PageRenderWorker` shared the live
  `fitz.Document` the main thread mutates/reads; PyMuPDF is not thread-safe →
  intermittent crashes. The worker now renders from its **own private copy**
  (opened from a decrypted, in-memory serialization of the document), so the
  background thread never touches the editable document. Access is fully isolated
  — no shared object across threads. Trade-off: a transient extra in-memory copy
  for the renderer and a serialize step after each edit. (The thumbnail sidebar
  renders on the main thread via `QTimer`, so it doesn't reintroduce the race.)

---

## ✅ Done (high — broken features)

- [x] **#5 — Bookmark edits now persist.** Rename/delete in the sidebar rebuild the
  TOC and call `set_toc`; "Add Bookmark Here" adds at the current page via
  `add_bookmark`. Changes mark the document modified and survive save/reopen.
  (Bookmark edits are not yet on the undo stack — minor follow-up.)
- [x] **#6 — Page drag-drop reorder wired.** Thumbnails are draggable; dropping
  reorders the document via `PDFDocument.reorder_pages()` (computed full target
  order + `Document.select`), undoable through the snapshot mechanism.
- [x] **#7 — Edit-menu clipboard ops do real work.** Copy/Select-All copy text;
  Paste inserts clipboard text as a text box on the current page; Cut/Delete erase
  the selected region (undoable until saved). Empty/no-selection cases inform the
  user instead of silently doing nothing.

---

## 🟡 Medium — dead code & documentation drift

- [ ] **#8 — ~3,350 LOC of dead code advertised as features.** Decide per module:
  wire it up or delete it.
  - [forms/form_field.py](../forms/form_field.py) (686) — full form system, never imported
  - [annotations/base.py](../annotations/base.py) (591) — parallel annotation system, unused
  - [core/converters/to_word.py](../core/converters/to_word.py) (321), [to_image.py](../core/converters/to_image.py) (296) — unused; Word export reimplemented inline
  - [core/operations/ocr.py](../core/operations/ocr.py) (367) — unused; OCR reimplemented inline
  - [ui/dialogs/merge_dialog.py](../ui/dialogs/merge_dialog.py) (294), [split_dialog.py](../ui/dialogs/split_dialog.py) (374), [settings_dialog.py](../ui/dialogs/settings_dialog.py) (419) — unused (no Settings menu)
  - Also dead: `TransactionManager`/`CompoundCommand` and `PDFDocument._temp_files`
- [ ] **#9 — Autosave / crash recovery advertised but absent.** Config/README/SettingsDialog
  describe it ([config.py:44](../config.py#L44), [config.py:163](../config.py#L163)) but no
  timer performs it and `SettingsDialog` is never shown. Implement it or drop the claims.
- [ ] **#10 — Docs overstate capabilities; 3 stale, contradictory reports.** README
  claims Excel/PowerPoint/HTML conversion, digital signatures, multi-tab — none
  implemented. Reconcile README and replace/delete `CODE_QUALITY_REPORT.md`,
  `docs/BROKEN_FEATURES_REPORT.md`, `docs/FEATURE_AUDIT_REPORT.md` with current docs.

---

## 🟢 Low — quality nits

- [ ] **Inconsistent error handling.** Logging added in [utils/history.py](../utils/history.py)
  and the [pdf_viewer.py](../ui/pdf_viewer.py) render paths, but the older command
  classes still swallow with `except Exception: return False`, and several
  main-thread interaction handlers in `pdf_viewer.py` still use `print(...)` for
  errors (annotation/text helpers).
- [ ] **Misleading `@dataclass` + custom `__init__`** on the command classes
  ([utils/history.py](../utils/history.py)) — the generated init is overridden, fields are dead.
- [ ] **Encapsulation break.** `AnnotationAddCommand._create_stamp_annotation` sets
  `self.document._is_modified = True` directly; `mark_modified()` exists.
  [utils/history.py](../utils/history.py)
- [ ] **Cross-platform claims vs Windows-only code.** `subprocess.Popen(['start', ...], shell=True)`
  ([ui/handlers/file_handler.py:393](../ui/handlers/file_handler.py#L393)) and the "Segoe UI"
  default font; README claims macOS/Linux support. (`send2trash` dependency appears unused.)
- [ ] **OCR text layer is mispositioned.** All page text is inserted at a single point
  ([ui/handlers/tools_handler.py](../ui/handlers/tools_handler.py)), so search-highlight
  rects won't align with the visible words.
- [ ] **Compress-in-place is a no-op.** `compress()` with no output path routes to a
  same-file incremental save that doesn't shrink the file. [core/pdf_document.py](../core/pdf_document.py)
- [ ] **ruff: 2 unused imports** (`QRectF`, `QBrush`) in
  [ui/dialogs/remove_header_footer_dialog.py:11-12](../ui/dialogs/remove_header_footer_dialog.py#L11-L12).

---

## Suggested next order

1. **#4** render-thread safety (stability; partially started)
2. **#5 / #6 / #7** broken UI features users expect to work
3. **#8 / #9 / #10** dead-code/doc cleanup (decide scope first)
4. Low-severity nits (can be bundled)
