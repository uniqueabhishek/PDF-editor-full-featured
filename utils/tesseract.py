"""Locate and configure the Tesseract OCR engine for pytesseract.

``pytesseract`` only wraps the native ``tesseract`` executable; it must be found
either on PATH or via an explicit path. Users who install the UB-Mannheim
Windows build often don't add it to PATH, so OCR fails with
``TesseractNotFoundError`` even though the engine is installed. This module
points pytesseract at a bundled copy (for packaged builds) or a standard install
location when the binary isn't already reachable, so OCR works without the user
editing their PATH.
"""
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Iterator, Optional

logger = logging.getLogger(__name__)


def _candidate_paths() -> Iterator[Path]:
    """Yield likely tesseract executable locations, most-preferred first."""
    exe = "tesseract.exe" if os.name == "nt" else "tesseract"

    # 1. Bundled alongside the app (packaged installer) or the frozen exe.
    bases = []
    if getattr(sys, "frozen", False):
        bases.append(Path(sys.executable).parent)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            bases.append(Path(meipass))
    # Source/repo root: utils/tesseract.py -> project root.
    bases.append(Path(__file__).resolve().parent.parent)
    for base in bases:
        yield base / "tesseract" / exe

    # 2. Standard install locations.
    if os.name == "nt":
        for env in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
            root = os.environ.get(env)
            if root:
                yield Path(root) / "Tesseract-OCR" / exe
        local = os.environ.get("LOCALAPPDATA")
        if local:
            # UB-Mannheim per-user install.
            yield Path(local) / "Programs" / "Tesseract-OCR" / exe
    else:
        for p in ("/usr/bin/tesseract", "/usr/local/bin/tesseract",
                  "/opt/homebrew/bin/tesseract"):
            yield Path(p)


def _locate() -> Optional[str]:
    """Return a path to a tesseract executable, or None if none is found."""
    found = shutil.which("tesseract")
    if found:
        return found
    for cand in _candidate_paths():
        try:
            if cand.is_file():
                return str(cand)
        except OSError:
            continue
    return None


def configure_tesseract() -> bool:
    """Ensure pytesseract can run the Tesseract engine.

    Returns True when a working tesseract is available (already reachable, or
    located here and wired up), False otherwise. Safe to call repeatedly; the
    version probe is cheap once it succeeds.
    """
    try:
        import pytesseract
    except ImportError:
        return False

    # Already working (on PATH, or configured by a previous call)?
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        pass

    found = _locate()
    if not found:
        return False

    pytesseract.pytesseract.tesseract_cmd = found
    # Point at a bundled tessdata folder next to the binary, if present.
    tessdata = Path(found).parent / "tessdata"
    if tessdata.is_dir():
        os.environ.setdefault("TESSDATA_PREFIX", str(tessdata))

    try:
        pytesseract.get_tesseract_version()
        logger.info("Configured Tesseract at %s", found)
        return True
    except Exception:
        logger.warning(
            "Found tesseract at %s but it failed to run", found, exc_info=True)
        return False
