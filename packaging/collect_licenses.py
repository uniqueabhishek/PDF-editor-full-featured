"""Write THIRD-PARTY-NOTICES.md for the Windows download.

Collects the licence files of every package the app ships with (the runtime
dependencies in pyproject.toml and everything they pull in), straight from the
installed packages, so the notices always match what was bundled.

    uv run python packaging/collect_licenses.py [source-url]
"""

import re
import sys
from importlib import metadata
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "packaging" / "build" / "THIRD-PARTY-NOTICES.md"
REPO = "https://github.com/uniqueabhishek/PDF-editor-full-featured"
# Packages whose metadata has no short licence name.
KNOWN = {"PyMuPDF": "AGPL-3.0 (or Artifex commercial)"}
LICENCE_FILE = re.compile(r"(LICEN[CS]E|COPYING|NOTICE)", re.IGNORECASE)


def _name(requirement: str) -> str:
    return re.split(r"[\s<>=!~;\[(]", requirement, maxsplit=1)[0].lower()


def runtime_distributions() -> list[metadata.Distribution]:
    """The runtime dependencies and everything they require, without extras."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    pending = [_name(r) for r in project["dependencies"]]
    found: dict[str, metadata.Distribution] = {}
    while pending:
        name = pending.pop()
        if name in found:
            continue
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue  # a platform-specific requirement not installed here
        found[name] = dist
        for req in dist.requires or []:
            if "extra ==" not in req:
                pending.append(_name(req))
    return sorted(found.values(), key=lambda d: d.metadata["Name"].lower())


def licence_texts(dist: metadata.Distribution) -> list[tuple[str, str]]:
    texts = []
    for file in dist.files or []:
        if LICENCE_FILE.search(file.name) and ".dist-info" in str(file):
            text = Path(str(file.locate())).read_text(encoding="utf-8", errors="replace")
            if text:
                texts.append((file.name, text.strip()))
    return texts


def main() -> None:
    source = sys.argv[1] if len(sys.argv) > 1 else f"{REPO}/tree/main"
    dists = runtime_distributions()
    lines = [
        "# Third-party notices",
        "",
        "Open PDF Editor's own code is under the MIT License (see `LICENSE`).",
        "",
        "This Windows download also contains the packages below. Because it includes",
        "PyMuPDF (GNU AGPL v3) and PyQt6 (GNU GPL v3), **the download as a whole is",
        "distributed under the GNU Affero General Public License v3**. The complete",
        f"source code for this exact build is available at: {source}",
        "",
        "Qt itself (in the `PyQt6/Qt6` folder) is under the GNU LGPL v3; its DLLs are",
        "separate files that can be replaced with a compatible build.",
        "",
        "| Package | Version | Licence |",
        "|---|---|---|",
    ]
    for dist in dists:
        meta = dist.metadata
        licence = KNOWN.get(meta["Name"], "")
        for key in ("License-Expression", "License"):
            if not licence and key in meta:
                licence = meta[key]
        if not licence or len(licence) > 60:
            classifiers = [
                c.split(" :: ")[-1]
                for c in meta.get_all("Classifier") or []
                if c.startswith("License ::")
            ]
            licence = ", ".join(classifiers) or "see text below"
        lines.append(f"| {meta['Name']} | {dist.version} | {licence} |")
    for dist in dists:
        for filename, text in licence_texts(dist):
            lines += [
                "",
                f"## {dist.metadata['Name']} {dist.version}: {filename}",
                "",
                "```text",
                text,
                "```",
            ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(dists)} packages")


if __name__ == "__main__":
    main()
