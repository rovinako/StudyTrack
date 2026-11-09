"""Run only our fixed Racket interpreter. User input is JSON data, never code."""

import json
import os
from pathlib import Path
import shutil
import subprocess
from .functional import grade_summary, allocate

RUNNER = Path(__file__).resolve().parents[1] / "racket" / "runner.rkt"


def executable():
    return os.getenv("RACKET_BIN") or shutil.which("racket")


def calculate(operation, data):
    binary = executable()
    if not binary:
        value = (
            grade_summary(data["items"])
            if operation == "grade"
            else allocate(data["tasks"], data["available"])
        )
        return value, "Python functional fallback"
    try:
        process = subprocess.run(
            [binary, str(RUNNER)],
            input=json.dumps({"operation": operation, **data}),
            text=True,
            capture_output=True,
            timeout=8,
            check=False,
        )
        if process.returncode:
            raise ValueError(
                "Racket rejected the calculation. Check the input and runtime."
            )
        return json.loads(process.stdout), "Racket DSL"
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
        raise ValueError(
            "The Racket calculation could not finish. Please try again."
        ) from error
