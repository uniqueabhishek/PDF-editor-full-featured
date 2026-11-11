# Security policy

## Supported versions

Security fixes go into the latest code on the `main` branch and the newest release.

## Reporting a vulnerability

Please do **not** open a public issue for a security problem.

Report it privately through GitHub instead:
[Security → Report a vulnerability](https://github.com/uniqueabhishek/PDF-editor-full-featured/security/advisories/new).

Include:

1. What the problem is and what an attacker could do with it.
2. Steps to reproduce it, ideally with a sample PDF.
3. The app version or commit and your operating system.

You should get a first reply within a week. Once a fix is ready, it is released and the report is credited to you unless you prefer otherwise.

## Scope

Ultra PDF Editor works offline and opens files you choose. The most relevant problems are PDFs crafted to crash the app, run code, or read or write files they should not, and redaction or encryption that does not remove or protect content as promised.

Flaws in PyMuPDF, Qt or Tesseract themselves should also be reported to those projects.
