#!/bin/bash
set -e
cd -- "$(dirname -- "$0")"
if [ -x ../../work/studytrack-venv/bin/python ]; then
  studytrack_python=../../work/studytrack-venv/bin/python
else
  if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt
  fi
  studytrack_python=.venv/bin/python
fi
if ! "$studytrack_python" -c "import pypdf, defusedxml" >/dev/null 2>&1; then
  "$studytrack_python" -m pip install -r requirements.txt
fi
if [ -z "${RACKET_BIN:-}" ] && [ -x ../../work/racket-runtime/racket/bin/racket ]; then
  export RACKET_BIN="$(cd ../../work/racket-runtime/racket/bin && pwd)/racket"
fi
printf '%s\n' 'Open http://127.0.0.1:5055 in your browser. Press Ctrl+C to stop.'
exec "$studytrack_python" app.py
