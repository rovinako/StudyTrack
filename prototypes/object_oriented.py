"""Objects own assignment validation, relationships and grade rules."""

from studytrack.domain import Assignment, Course


class Gradebook:
    def __init__(self, course):
        self.course = course
        self._assignments = ()

    @property
    def assignments(self):
        return self._assignments

    def add(self, assignment):
        if sum(a.weight for a in self._assignments) + assignment.weight > 100 + 1e-6:
            raise ValueError("Weights exceed 100%.")
        self._assignments += (assignment,)

    def current_grade(self):
        graded = [a for a in self._assignments if a.score is not None]
        total = sum(a.weight for a in graded)
        return sum(a.score * a.weight for a in graded) / total if total else None


if __name__ == "__main__":
    book = Gradebook(Course("CMPSC 460"))
    book.add(Assignment("Homework", "2026-04-20", 40, 60, 80))
    book.add(Assignment("Exam", "2026-04-22", 60, 90, 90))
    print(book.current_grade())
