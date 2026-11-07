# AGENTS.md — SalmanPDF

Rules for every AI agent working in this repository. The owner's global
rules (think before coding, simplicity first, surgical changes only, no
hallucination, verify your work, confirmation for destructive actions,
honest reporting) apply in full — this file adds SalmanPDF-specific facts
and invariants on top of them.

## Project

- **What this is:** SalmanPDF, a desktop PDF / Office conversion and
  editing tool (Python, PyMuPDF) for Windows, macOS, and Linux.
- **Owner / credit:** the credit line reads exactly
  `created by Ricco Abu Salman` — never change its wording or add
  parentheses.
- **User-facing language:** Indonesian UI and messages.

## Layout & commands

- App package: `salmanpdf/`; entry point: `main.py`; tests: `tests/`
  (run `python -m pytest tests/` before reporting any change as done).
- Builds: `build-windows.bat`, `build-mac.sh`, `build-deb.sh`.
- Current release: v0.12.1 (see CHANGELOG.md — update it with every
  user-visible change).

## Invariants — do not break these

- **Frozen-build startup guard is load-bearing.** PyMuPDF auto-imports
  its `pymupdf.layout` subpackage, whose ONNX model files PyInstaller
  does not bundle; without protection the frozen app crashes at startup
  (this shipped broken in v0.12.0). The guard in `salmanpdf/__init__.py`
  (`sys.modules.setdefault("pymupdf.layout", None)` when `sys.frozen`)
  and the PyInstaller flags `--exclude-module pymupdf.layout
  --exclude-module onnxruntime` must stay in every build command. Never
  remove or "clean them up".
- **.deb builds must use `dpkg-deb -Zgzip -b`.** This project's debs are
  installed on Linux Mint whose dpkg cannot read zstd-compressed
  packages.
- **Office conversion on Windows** goes through Microsoft Office COM,
  with LibreOffice as the fallback. Do not swap this order or drop the
  fallback.
- GitHub snapshot pushes do not preserve file modes: after a clone,
  scripts may need `chmod +x *.sh` (or run them as `bash script.sh`).
  Keep this note accurate in user-facing docs.
