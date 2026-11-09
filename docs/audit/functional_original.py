"""Pure transformations used by the app when Racket is not installed.

No input mutation or I/O. The two Racket DSLs implement the same rules.
"""
from functools import reduce


def grade_summary(items):
    graded = tuple(filter(lambda item: item['score'] is not None, items))
    weight = sum(map(lambda item: item['weight'], graded))
    earned = sum(map(lambda item: item['score'] * item['weight'] / 100, graded))
    return {'current': earned * 100 / weight if weight else None,
            'earned': earned, 'graded_weight': weight,
            'configured_weight': sum(map(lambda item: item['weight'], items))}


def allocate(tasks, available):
    def step(state, task):
        remaining, result = state
        duration = min(remaining, task['minutes'])
        return (remaining - duration, result + ({'id': task['id'], 'minutes': duration},) if duration else result)
    remaining, sessions = reduce(step, tasks, (available, ()))
    return {'sessions': list(sessions), 'unused_minutes': remaining}
