"""Reproduce the four prototype outputs. Run from the unzipped source folder."""
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

cwd = Path.cwd()
if not (cwd / "prototypes").is_dir():
    raise SystemExit("Run this command from the extracted StudyTrack source folder.")
checks = [
    ("Imperative", [sys.executable, "-m", "prototypes.imperative"], "86.0", None),
    ("Object-oriented", [sys.executable, "-m", "prototypes.object_oriented"], "86.0", None),
    ("Functional", [os.getenv("RACKET_BIN", "racket"), "prototypes/functional.rkt"], "86.0", None),
    ("Declarative", ["sqlite3", ":memory:"], "A", (cwd / "prototypes/declarative.sql").read_text()),
]
results = []
for label, command, expected, stdin in checks:
    result = subprocess.run(command, cwd=cwd, input=stdin, text=True, capture_output=True, timeout=30)
    ok = result.returncode == 0 and result.stdout.strip() == expected
    results.append({"prototype": label, "command": command[1:], "expected": expected, "actual": result.stdout.strip(), "passed": ok})
    if not ok:
        raise SystemExit(f"{label} failed: {result.stderr or result.stdout}")
print(json.dumps({"review_date": date.today().isoformat(), "results": results}, indent=2))
