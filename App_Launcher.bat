@echo off
cd /d "%~dp0"
start "" "%USERPROFILE%\.local\bin\uv.exe" run --env-file .env Ultra_PDF_Editor.py
