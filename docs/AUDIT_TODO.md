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

- [x] **#8 — Dead code advertised as features.** Done across the steps below
  (~2,350 LOC of dead code removed; merge/split/settings turned into real features).
  - [x] **Pure duplicates removed** — `core/converters/to_word.py`, `to_image.py`
    and `core/operations/ocr.py` (plus their package `__init__.py`). These
    reimplemented functionality the app already runs inline (Word export in
    `file_handler`, OCR in `tools_handler`, image render via
    `PDFDocument.render_page_to_image`). ~985 LOC removed; no behavior change.
    (Stale doc references to these now feed into #10.)
  - [x] **forms/ deleted** — the 686-line form system was never imported, had no
    UI, and carried real bugs (colliding widget-type constants, stub
    `remove_field`/`flatten`, no FDF/XFDF). Removed the package and dropped the
    forms claims from the README. Rebuild deliberately if forms become a priority.
  - [x] **annotations/base.py deleted** — a 591-line parallel annotation model
    (Annotation classes + serialization) that was never imported; the annotation
    feature runs via `PDFDocument` + `AnnotationAddCommand`. Removed the package
    and its README structure entry. (The annotation *feature* is unaffected.)
  - [x] **MergeDialog / SplitDialog wired up** — both refactored to pure UI/option
    collectors (their duplicate worker threads removed); the work routes through
    the tested `PDFDocument.merge_pdfs` / `split_by_*` methods on the in-memory
    document. Adds real features: merge reordering + per-file bookmarks, and split
    by every-N-pages / custom ranges / bookmarks (previously only 1-page-per-file).
    `merge_pdfs` gained `add_bookmarks`/`compress`; added `split_by_bookmarks`.
  - [x] **SettingsDialog wired up** — added **Edit → Preferences…** (Ctrl+,). The
    dialog was trimmed to only settings that take effect (theme, sidebar width,
    confirm-close, auto-save), removing the decorative tabs/controls. Theme and
    sidebar width apply live; theme application is shared via new `ui/theme.py`
    (also used at startup). Done together with #9.
  - [x] **Small dead bits removed** — `TransactionManager` + `CompoundCommand`
    (never instantiated) and the unused `PageMoveCommand` (reorder uses the
    snapshot command); `CommandType` trimmed to the members live commands use
    (dropping the orphaned `FORM_FIELD_*`, `TEXT_*`, `IMAGE_*`, `BOOKMARK_*`,
    `MERGE`/`SPLIT`); and `PDFDocument._temp_files` (never populated) with its
    dead cleanup loop in `close()`.
- [x] **#9 — Autosave / crash recovery implemented.** A `QTimer` writes a recovery
  copy (`AUTOSAVE_DIR/recovery.pdf` + `recovery.json`) of the open document while
  it has unsaved changes, at the configured interval. On startup the app offers to
  restore a leftover recovery (i.e. after a crash) and retargets Save to the
  original file via `PDFDocument.set_filepath`. Recovery is cleared on clean
  save/close/open/new and on clean exit. Driven by the Preferences auto-save toggle.
- [x] **#10 — Docs reconciled.** README corrected — dropped multi-tab, digital
  signatures, and the Word/Excel/PowerPoint/HTML/PDF-A conversion table; the Export
  section now lists images/Word/text only, and the (now real) auto-save claim
  stays. Deleted the 3 stale reports (`CODE_QUALITY_REPORT.md`,
  `docs/BROKEN_FEATURES_REPORT.md`, `docs/FEATURE_AUDIT_REPORT.md`) in favour of
  this living checklist, and fixed deleted-module references in `index.md`,
  `API_REFERENCE.md` (removed the OCRProcessor / annotation / form / converter
  sections), `ARCHITECTURE.md` and `CONTRIBUTING.md` (structure trees + extension
  guidance). Residual: `USER_GUIDE.md` prose still describes a few absent niceties.

---

## 🟢 Low — quality nits (done)

- [x] **Error handling** — the `print(...)` error handlers in `pdf_viewer.py` and the
  stamp command now use logging. (Older undo commands still return False quietly;
  acceptable for the command pattern.)
- [x] **Misleading `@dataclass` + custom `__init__`** removed from the command
  classes (and the unused `dataclass` import).
- [x] **Encapsulation** — the stamp command uses `PDFDocument.mark_modified()` instead
  of poking `_is_modified`.
- [x] **Cross-platform file open** — exported docs open via `os.startfile` / `open` /
  `xdg-open` instead of Windows-only shell `start`.
- [x] **OCR text layer** now positions each recognised word (via `image_to_data`).
- [x] **Compress-in-place** now forces a full rewrite so it actually shrinks the file.
- [x] **ruff** is clean across the project (the 2 unused dialog imports were removed).

Not pursued (would need real features / dependency tracing, not nits): `send2trash`
and other possibly-unused declared dependencies in `pyproject.toml`.

---

## Status

All audit items **#1–#10 are complete.** Remaining optional follow-ups: a full
`USER_GUIDE.md` prose pass, and pruning unused declared dependencies from
`pyproject.toml`.
