@echo off
cd /d "%~dp0"
start "" "%USERPROFILE%\.local\bin\uv.exe" run --env-file .env Open_PDF_Editor.py
