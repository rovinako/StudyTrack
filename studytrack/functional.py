"""Pure Python equivalents of the Racket DSLs, used when Racket is absent.

Each function returns a new result without changing its input or doing I/O.
"""

from functools import reduce
import math


def valid_number(value):
    return (
        isinstance(value, (float, int))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def valid_integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def valid_grade_item(item):
    weight = item["weight"]
    score = item["score"]
    weight_ok = valid_number(weight) and 0 < weight <= 100
    score_ok = score is None or (valid_number(score) and 0 <= score <= 100)
    return weight_ok and score_ok


def grade_summary(items):
    items = tuple(items)
    if not all(valid_grade_item(item) for item in items):
        raise ValueError("Invalid score or weight.")

    total_weight = sum(item["weight"] for item in items)
    if total_weight > 100 + 1e-6:
        raise ValueError("Assignment weights cannot add up to more than 100%.")

    # Missing scores are excluded. A score of zero still counts.
    graded = tuple(item for item in items if item["score"] is not None)
    graded_weight = sum(item["weight"] for item in graded)
    earned = sum(item["score"] * item["weight"] / 100 for item in graded)
    current = earned * 100 / graded_weight if graded_weight else None
    return {
        "current": current,
        "earned": earned,
        "graded_weight": graded_weight,
        "configured_weight": total_weight,
    }


def allocate(tasks, available):
    tasks = tuple(tasks)
    if not valid_integer(available) or not 0 <= available <= 1440:
        raise ValueError("Available minutes must be a whole number from 0 to 1440.")
    if any(
        not valid_integer(task["id"])
        or task["id"] <= 0
        or not valid_integer(task["minutes"])
        or not 1 <= task["minutes"] <= 1440
        for task in tasks
    ):
        raise ValueError("Task IDs and minutes must be valid positive integers.")
    if len({task["id"] for task in tasks}) != len(tasks):
        raise ValueError("Task IDs must be unique.")

    def add_session(state, task):
        remaining, sessions = state
        duration = min(remaining, task["minutes"])
        if duration == 0:
            return state
        session = {"id": task["id"], "minutes": duration}
        return remaining - duration, sessions + (session,)

    remaining, sessions = reduce(add_session, tasks, (available, ()))
    return {"sessions": list(sessions), "unused_minutes": remaining}
