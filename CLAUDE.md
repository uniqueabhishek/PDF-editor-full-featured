# CLAUDE.md

PyQt6 PDF editor on PyMuPDF with OCR via pytesseract. Environment is
uv-managed: `uv sync`, then `uv run ultra-pdf-editor`; tests with `uv run pytest`.

`[tool.uv] python-preference = "only-system"` is deliberate and must stay: uv's
managed CPython builds are unsigned and Smart App Control blocks their
`pythonw.exe`. Only a python.org interpreter may be used here.

## Toolchain (migration pending)

The standard for every Python project on this machine is **uv + ruff + mypy**,
with Pylance doing types inside VS Code. The finished reference is
`D:\D Desktop\PY __ CA Office Suite` (a Qt app too): copy its `[tool.ruff]`,
`[tool.mypy]` and `[tool.pyright]` blocks, its `.vscode/` folder, and the
"Lint, Format and Types" section of its `CLAUDE.md`.

### Where this project stands (checked 2026-09-05)

| Piece | Status |
|---|---|
| uv | done (uv.lock, .python-version, dev group) |
| ruff | installed in the dev group (`ruff>=0.1.0`) but has no `[tool.ruff]` section, so it runs on 88-column defaults with the minimal rule set |
| mypy | missing |
| VS Code ruff-on-save + extension recommendations | missing |
| pre-commit | missing |

### At session start

If any row above is not "done", tell the user in one or two lines and offer to
run the migration. Do not start unasked. When it is done, replace this section
with the three commands that apply.

### Migration steps

1. Bump the pin: `uv add --group dev "ruff>=0.16" mypy`.
2. Add to pyproject.toml (line length 100 unless the code was already wrapped
   at another width):
   ```toml
   [tool.ruff]
   line-length = 100
   target-version = "py310"

   [tool.ruff.lint]
   select = ["E", "W", "F", "I", "PL", "UP", "B", "BLE", "SIM", "RUF"]
   ignore = ["PLR2004", "PLR0913", "E501"]

   [tool.ruff.lint.per-file-ignores]
   "tests/**" = ["PLR0915"]

   [tool.ruff.format]
   quote-style = "double"

   [tool.mypy]
   python_version = "3.10"
   ignore_missing_imports = true   # pytesseract, send2trash, darkdetect have no stubs
   check_untyped_defs = true
   exclude = "^(\\.venv|build|dist)/"
   ```
3. `uv run ruff format .`, then `uv run ruff check --fix .`, fix the rest by hand.
   Expect PLR0915 on the window's layout method and BLE001 on the top-level
   `except Exception` guards around PyMuPDF and Tesseract calls; annotate those
   with `# noqa: <code>` and a reason instead of restructuring.
4. `uv run mypy .` and fix what it finds. PyQt6 ships its own stubs, so no
   extra package is needed.
5. Copy `.vscode/settings.json` and `.vscode/extensions.json` from the reference
   project.
6. Optionally copy `D:\D Desktop\PY___WhatsApp Scheduler\.pre-commit-config.yaml`
   so ruff and pytest run on every commit.

### Newer tools to keep in view

- **ty** (Astral) and **pyrefly** (Meta): Rust type checkers, out of beta in
  2026, far faster than mypy. No mypy plugins are needed here, so `ty` is a
  candidate for the CLI checker once its PyQt6 stub handling is confirmed.
- **uv_build** as a build backend if `[project.scripts]` ever needs a wheel.
- A task runner (`just` or `poethepoet`) once there are more than three check
  commands.

## Never

- Install with pip or from the editor package UI; the environment is locked by
  uv.lock. Use `uv add` / `uv remove`.
- Remove `python-preference = "only-system"` (see the top of this file).
