# Ultra PDF Editor — Improvements Audit

Second-pass review of the v1.0.0 tree, after the original `AUDIT_TODO.md`
remediation (#1–#10) was completed. These are the next layer of findings:
correctness bugs, privacy/security gaps, performance, dead code, and test
coverage. Each item is tracked as its own commit.

**Created:** 2026-05-31
**Status legend:** `[ ]` planned · `[x]` done

This document is a living checklist; each box is ticked in the same commit that
implements the fix.

---

## 🔴 Correctness bugs

- [ ] **#A1 — "Find & Replace" is a no-op.** `_do_replace` / `_do_replace_all`
  (`ui/handlers/edit_handler.py`) only show an info dialog, yet Ctrl+H and a full
  `FindReplaceDialog` are wired to them. Either implement redaction-based
  replacement (redact the found rect, re-insert the replacement text) or remove
  the Replace surface. **Fix:** implement redaction-based replace on the model
  (`PDFDocument.replace_text`) and wire it through an undoable snapshot op.

- [x] **#A2 — "Case sensitive" search does nothing.**
  `PDFDocument.search_text` (`core/pdf_document.py`) sets
  `flags = 0 if case_sensitive else TEXT_PRESERVE_WHITESPACE`.
  `TEXT_PRESERVE_WHITESPACE` is an extraction flag, not a case toggle, and
  PyMuPDF `search_for` is case-insensitive regardless. **Fix:** post-filter
  matches against extracted span text when case-sensitive is requested.

- [x] **#A3 — Page reorder strands bookmarks.**
  `reorder_pages` used `doc.select`, which discards the TOC entirely, so a
  drag-reorder lost every bookmark. (`move_page` was verified to already remap
  the TOC correctly, so it needed no change.) **Fixed:** capture the TOC before
  `select` and remap each entry's page through the permutation.

## 🟠 Security / privacy

- [x] **#B1 — Autosave writes decrypted copies of encrypted PDFs to disk.**
  `_autosave` → `save_copy(AUTOSAVE_DIR/recovery.pdf)` and `save_copy` saves with
  no encryption, so editing a password-protected PDF leaks plaintext to
  `~/.ultra_pdf_editor/autosave/`. **Fix:** skip the unencrypted recovery write
  for protected documents (and document the behaviour).

- [x] **#B2 — No logging is configured.** Modules log heavily and error dialogs
  say "See log for details," but `main()` never calls `logging.basicConfig`, so
  those records have no destination. **Fix:** configure a rotating log file in
  `CONFIG_DIR`.

## 🟡 Performance

- [x] **#C1 — Every edit re-serializes the whole document.**
  `refresh` / `invalidate_render_copy` call `doc.tobytes()` to hand the render
  worker a fresh copy; on large PDFs that is the dominant per-edit cost.
  **Fix:** debounce the worker re-serialize (the synchronous current-page render
  already gives instant feedback).

- [x] **#C2 — Snapshot undo can balloon memory.**
  `DocumentSnapshotCommand` keeps full `_before` and `_after` PDF bytes, up to
  `UNDO_HISTORY_SIZE = 100` commands. **Fix:** add a total-bytes budget that
  evicts the oldest snapshot commands.

- [x] **#C3 — Page cache is not true LRU.** Eviction drops the oldest *inserted*
  entry; cache hits don't reorder, so a frequently-viewed page can be evicted.
  **Fix:** `OrderedDict` + `move_to_end` on hit.

## 🟢 Dead code / maintainability

- [x] **#D1 — ~240 lines of dead annotation code in the viewer.**
  `_create_text_markup_annotation`, `_create_shape_annotation`,
  `_create_line_annotation`, `_create_freehand_annotation_from_points` have no
  callers — superseded by the undoable `_request_annotation` →
  `AnnotationAddCommand` pipeline. **Fix:** remove them.

- [ ] **#D2 — Long operations run on the GUI thread.** OCR, Word export and print
  loop with manual `QApplication.processEvents()`, freezing the window.
  **Fix:** move them to `QThread` workers following the `PageRenderWorker`
  pattern.

- [x] **#D3 — The mixin contract is invisible to type checkers.** All six handler
  mixins reference `self._document`, `self._viewer`, … defined on `MainWindow`.
  **Fix:** add a `typing.Protocol` documenting the shared surface.

- [ ] **#D4 — Unused declared dependencies.** `pyproject.toml` declares pikepdf,
  reportlab, pdf2image, openpyxl, python-pptx, beautifulsoup4, lxml, pdfplumber,
  cryptography, natsort, send2trash — none imported in the runtime tree.
  **Fix:** drop the unused ones; keep what optional features need.

- [ ] **#D5 — Assorted nits.** `PDFDocument.__del__` calling `close()` is a
  fragile shutdown backstop; `config` creates directories at import time (import
  side effects in tests); `PageRenderWorker.run` busy-polls with `msleep(10)`.
  **Fix:** guard `__del__`, make config dir creation explicit/lazy, replace the
  poll with a wait condition.

## 🧪 Testing

- [ ] **#E1 — No GUI/handler tests.** Model/history/config/utils are well
  covered, but the save→detach→reattach flow, undo/redo view-sync, and the render
  worker are untested. **Fix:** add `pytest-qt` smoke tests.

---

## Status

Tracking in progress — see commit history for per-item changes.
