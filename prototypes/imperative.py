"""Explicit loops, validation, sequence, and mutable local accumulators."""

import math


def weighted_grade(items):
    total_weight = 0
    total_points = 0
    if not items:
        raise ValueError("At least one graded item is required.")
    for score, weight in items:
        if (
            not math.isfinite(score)
            or not math.isfinite(weight)
            or not 0 <= score <= 100
            or not 0 < weight <= 100
        ):
            raise ValueError("Invalid score or weight.")
        total_points += score * weight
        total_weight += weight
    if abs(total_weight - 100) > 1e-6:
        raise ValueError("This complete-course prototype requires 100% total weight.")
    return total_points / total_weight


if __name__ == "__main__":
    print(weighted_grade([(80, 40), (90, 60)]))
