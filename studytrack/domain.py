"""Object-oriented domain: objects enforce rules before data reaches SQLite."""

from dataclasses import dataclass
from datetime import date
import math


def number(value, label, minimum, maximum):
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number.") from None
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ValueError(f"{label} must be between {minimum:g} and {maximum:g}.")
    return result


def name(value, label, maximum=100):
    result = str(value or "").strip()
    if not result or len(result) > maximum:
        raise ValueError(f"{label} must contain 1–{maximum} characters.")
    return result


@dataclass(frozen=True)
class Course:
    title: str
    target: float = 90

    def __post_init__(self):
        object.__setattr__(self, "title", name(self.title, "Course name"))
        object.__setattr__(self, "target", number(self.target, "Target grade", 0, 100))

    def remaining_weight(self, assignments):
        return max(0, 100 - sum(a["weight"] for a in assignments))


@dataclass(frozen=True)
class Assignment:
    title: str
    due: str
    weight: float
    minutes: int
    score: float | None = None

    def __post_init__(self):
        object.__setattr__(self, "title", name(self.title, "Assignment name"))
        try:
            parsed = date.fromisoformat(self.due)
        except (ValueError, TypeError):
            raise ValueError("Enter a valid due date.") from None
        object.__setattr__(self, "due", parsed.isoformat())
        object.__setattr__(self, "weight", number(self.weight, "Weight", 0.01, 100))
        minutes = number(self.minutes, "Study minutes", 1, 1440)
        if not minutes.is_integer():
            raise ValueError("Study minutes must be a whole number.")
        object.__setattr__(self, "minutes", int(minutes))
        if self.score is not None:
            object.__setattr__(self, "score", number(self.score, "Score", 0, 100))
