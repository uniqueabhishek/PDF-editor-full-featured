# Performance Audit — Ultra PDF Editor

Audit of the rendering pipeline, sidebar, document model, undo history, and
edit/refresh wiring. Findings are ordered by impact. Most of the architecture is
sound (background render worker isolated from the editable document, LRU pixmap
cache, debounced re-render); the issues below are the ones that degrade as page
count and document size grow.

Each issue lists the symptom, the root cause with file references, and the fix
applied in this branch.

---

## Critical

### 1. Every page allocated a full-resolution placeholder pixmap up front

**Symptom:** Opening a large document spikes memory into the gigabytes and is
slow before a single page is rendered; zooming churns memory.

**Cause:** `PageWidget.set_placeholder()` allocated a `QPixmap(width, height)` at
the full *zoomed pixel size* (a Letter page at 150 DPI ≈ 1275×1650 ≈ ~8 MB as a
32-bit pixmap), filled it white, and painted a border — for **every** page, eagerly,
in `_create_page_widgets()`. `_render_all_pages()` re-allocated all of them on
every zoom change. A 200-page document allocated ~1.5–2 GB of placeholder pixmaps
that are never displayed once the real render arrives.

- `ui/pdf_viewer.py` — `PageWidget.set_placeholder`, `_create_page_widgets`, `_render_all_pages`

**Fix:** Placeholders now cost zero pixels. The widget reserves geometry with
`setFixedSize` and clears its pixmap; the existing QLabel stylesheet
(`background-color: white; border: 1px solid #ccc`) paints the white page and
border. Visually identical, no per-page pixmap allocation.

### 2. Whole-document re-compression to feed the render worker

**Symptom:** Each edit pause re-serializes (and re-compresses) the entire document
to hand the background render worker a fresh copy — seconds of CPU on a large,
image-heavy PDF.

**Cause:** `_render_source()` used `doc.tobytes(garbage=0, deflate=True, …)`.
`deflate=True` re-compresses every stream; the bytes are transient and only used
in-memory by the worker, so compression buys nothing and costs the most.

- `ui/pdf_viewer.py` — `_render_source`

**Fix:** Serialize the transient worker copy with `deflate=False`. The worker
doesn't care about size; this removes the dominant cost of each resync.

### 3. Annotations panel re-scans the whole document on every edit

**Symptom:** Adding one highlight (or any modification) walks every page and
rebuilds the entire annotations list — O(pages) per edit.

**Cause:** `_on_document_modified` → `Sidebar.refresh()` → `AnnotationPanel.refresh()`
→ `set_document()` → `_load_annotations()`, which loops every page calling
`page.annots()`. It also stored **live `fitz.Annot` objects** that dangle after an
undo/redo snapshot-restore swaps the underlying document.

- `ui/main_window.py` — `_on_document_modified`
- `ui/sidebar.py` — `AnnotationPanel._load_annotations`, `refresh`, `set_document`

**Fix:** The panel now refreshes lazily. A modification only marks the panel dirty;
the full rescan happens when the Annotations tab is actually shown (or immediately
if it's already visible). The dangling live-`annot` list was removed (the list
widget already carries page+xref, which is what callers use).

---

## High

### 4. Snapshot-based undo serializes the whole document twice per destructive op

**Symptom:** Redact / crop / watermark / OCR / header-footer freezes the UI on
large documents — each runs two full-document serializations on the GUI thread.

**Cause:** `DocumentSnapshotCommand.execute()` snapshots before *and* after, and
`PDFDocument.snapshot()` used `tobytes(garbage=3, deflate=True)`. `garbage=3` runs
the expensive duplicate-stream-merge pass, which a round-trip snapshot does not
need.

- `core/pdf_document.py` — `snapshot`
- `utils/history.py` — `DocumentSnapshotCommand`

**Fix:** Snapshots use `garbage=1` (cheap removal of unused objects) instead of
`garbage=3`, keeping `deflate=True` so the undo memory budget still holds plenty
of history. Drops the per-op cost substantially.

### 5. Auto-save is a full synchronous save on the UI thread

**Symptom:** Every 5 minutes the window can freeze mid-edit while the recovery
copy is written.

**Cause:** `_autosave` → `save_copy()` ran `doc.save(garbage=4, deflate=True)` —
the heaviest save mode — synchronously on the GUI thread.

- `ui/main_window.py` — `_autosave`
- `core/pdf_document.py` — `save_copy`

**Fix:** Auto-save now serializes a recovery snapshot quickly on the GUI thread
(`garbage=0, deflate=False` — fast, PyMuPDF is not thread-safe so the serialize
must stay on the owning thread) and writes the bytes to disk on a background
thread. The expensive garbage-collect/deflate work is gone, and the disk I/O no
longer blocks the UI.

---

## Medium

### 6. O(n) scans over all page widgets on every scroll tick

**Symptom:** Scrolling a very large document does work proportional to the page
count on each scroll event.

**Cause:** `_update_current_page()` (un-debounced), `_request_visible_pages()`, and
the sidebar's `_render_visible_thumbnails()` looped over every widget. Pages are
laid out top-to-bottom with monotonically increasing y, so the loop can stop once
it passes the bottom of the viewport.

- `ui/pdf_viewer.py` — `_request_visible_pages`, `_update_current_page`
- `ui/sidebar.py` — `_render_visible_thumbnails`

**Fix:** Skip widgets above the viewport and `break` once a widget starts below it,
so each scroll touches only the visible band plus a constant margin.

### 7. Plain-text export runs on the GUI thread

**Symptom:** "Export as Text" hangs the window on a large document while every
page's text is extracted.

**Cause:** `_export_as_text` called `get_all_text()` synchronously. (The Word
export already uses the background-worker pattern; text export did not.)

- `ui/handlers/file_handler.py` — `_export_as_text`

**Fix:** Text export now runs on a `FunctionWorker` with a progress dialog, using
its own document copy opened from serialized bytes (the same safe pattern as Word
export). It reports per-page progress and is cancellable.

**Left synchronous by design:** in-document **search** (`search_text`) stays on the
GUI thread. It is interactive (find-as-you-type, find-next) and is re-run
synchronously right after replace operations that immediately navigate to a
result; PyMuPDF's `search_for` is fast for typical documents. Backgrounding it
would require restructuring the replace/navigate flow for little gain and real
UX/race risk.

---

## Status

| # | Issue | Status |
|---|-------|--------|
| 1 | Zero-cost page placeholders | Planned |
| 2 | Skip deflate for render-worker copy | Planned |
| 3 | Lazy annotation-panel refresh | Planned |
| 4 | Lighter undo snapshots | Planned |
| 5 | Offloaded / lighter auto-save | Planned |
| 6 | Early-exit visible-page/thumbnail scans | Planned |
| 7 | Background plain-text export | Planned |
