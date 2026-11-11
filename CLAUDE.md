# CLAUDE.md

PyQt6 PDF editor on PyMuPDF with OCR via pytesseract. Environment is
uv-managed: `uv sync`, then `uv run ultra-pdf-editor`; tests with `uv run pytest`.

`[tool.uv] python-preference = "only-system"` is deliberate and must stay: uv's
managed CPython builds are unsigned and Smart App Control blocks their
`pythonw.exe`. Only a python.org interpreter may be used here.

## Lint, format and types

- `uv run ruff format .` then `uv run ruff check --fix .` (config in pyproject.toml)
- `uv run mypy .` (app code only; tests are not type-checked)
- `uv run pytest -p no:faulthandler` (~1.5 min; faulthandler prints harmless QPrinter COM noise)

The pre-commit hooks run ruff and mypy on every commit and pytest on every
push. After a fresh clone: `uv run pre-commit install --hook-type pre-commit --hook-type pre-push`.

Silenced findings carry a reason next to the `# noqa`. Keep it that way.

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
