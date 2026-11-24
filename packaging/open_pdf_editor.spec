# PyInstaller build for the Windows download.
#
#   uv run pyinstaller packaging/open_pdf_editor.spec --noconfirm
#
# Produces dist/Open PDF Editor/ (one folder, not one file: it starts faster,
# never unpacks to a temp folder, and keeps Qt as separate DLLs that can be
# replaced, as Qt's LGPL licence asks).
# ruff: noqa
import tomllib
from pathlib import Path

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

ROOT = Path(SPECPATH).parent
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
NAME = "Open PDF Editor"
numbers = tuple(int(part) for part in VERSION.split(".")) + (0,) * (4 - len(VERSION.split(".")))

version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=numbers, prodvers=numbers),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",
                    [
                        StringStruct("CompanyName", "Open PDF Editor contributors"),
                        StringStruct("FileDescription", NAME),
                        StringStruct("FileVersion", VERSION),
                        StringStruct("InternalName", NAME),
                        StringStruct("LegalCopyright", "Open source: MIT (own code), AGPL v3 (this build)"),
                        StringStruct("OriginalFilename", f"{NAME}.exe"),
                        StringStruct("ProductName", NAME),
                        StringStruct("ProductVersion", VERSION),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

# Qt modules the app never imports; leaving them out keeps the download small.
UNUSED = [
    "tkinter",
    "PyQt6.QtQml",
    "PyQt6.QtQuick",
    "PyQt6.QtQuick3D",
    "PyQt6.QtQuickWidgets",
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtWebChannel",
    "PyQt6.QtWebSockets",
    "PyQt6.QtMultimedia",
    "PyQt6.QtMultimediaWidgets",
    "PyQt6.QtBluetooth",
    "PyQt6.QtNfc",
    "PyQt6.QtPositioning",
    "PyQt6.QtSensors",
    "PyQt6.QtSerialPort",
    "PyQt6.QtSql",
    "PyQt6.QtTest",
    "PyQt6.QtDesigner",
    "PyQt6.QtHelp",
    "PyQt6.QtOpenGL",
    "PyQt6.QtOpenGLWidgets",
    "PyQt6.QtPdf",
    "PyQt6.QtPdfWidgets",
    "PyQt6.QtSpatialAudio",
    "PyQt6.QtTextToSpeech",
    "PyQt6.QtRemoteObjects",
    "PyQt6.Qt3DCore",
]

a = Analysis(
    [str(ROOT / "Open_PDF_Editor.py")],
    pathex=[str(ROOT)],
    datas=[
        (str(ROOT / "resources" / "styles"), "resources/styles"),
        (str(ROOT / "resources" / "assets"), "resources/assets"),
        (str(ROOT / "LICENSE"), "."),
        (str(ROOT / "packaging" / "build" / "THIRD-PARTY-NOTICES.md"), "."),
    ],
    excludes=UNUSED,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=NAME,
    console=False,
    icon=str(ROOT / "resources" / "assets" / "OpenPDF.ico"),
    version=version_info,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name=NAME, upx=False)
