"""Page routes: read a form, validate it, save data, then show the result."""

from datetime import date, timedelta
import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from . import storage, ai
from .domain import Course, Assignment, number
from .racket_bridge import calculate
from .guidance import target_progress

web = Blueprint("web", __name__)


def course_record(course_id):
    result = storage.rows("SELECT * FROM courses WHERE id=?", (course_id,))
    if not result:
        abort(404)
    return result[0]


def course_cards():
    result = storage.rows("SELECT * FROM courses ORDER BY id")
    for course in result:
        assignments = storage.rows(
            "SELECT * FROM assignments WHERE course_id=? ORDER BY due,id",
            (course["id"],),
        )
        course["summary"], _ = calculate("grade", {"items": assignments})
        course["remaining"] = Course(
            course["title"], course["target"]
        ).remaining_weight(assignments)
        course["open_count"] = sum(not a["completed"] for a in assignments)
    return result


@web.get("/")
def dashboard():
    today = date.today()
    upcoming = storage.due_tasks(
        today.isoformat(), (today + timedelta(days=7)).isoformat()
    )
    overdue = storage.rows(
        """SELECT a.*,c.title AS course FROM assignments a JOIN courses c ON c.id=a.course_id
        WHERE a.completed=0 AND a.due < ? ORDER BY a.due,a.id""",
        (today.isoformat(),),
    )
    return render_template(
        "dashboard.html", courses=course_cards(), upcoming=upcoming, overdue=overdue
    )


@web.route("/courses", methods=["GET", "POST"])
def courses():
    if request.method == "POST":
        try:
            course = Course(request.form.get("title"), request.form.get("target"))
            with storage.db():
                cursor = storage.db().execute(
                    "INSERT INTO courses(title,target) VALUES (?,?)",
                    (course.title, course.target),
                )
            flash("Course added.", "success")
            return redirect(url_for("web.course_detail", course_id=cursor.lastrowid))
        except ValueError as error:
            flash(str(error), "error")
        except sqlite3.IntegrityError:
            flash("A course with that name already exists.", "error")
        return redirect(url_for("web.courses"))
    return render_template("courses.html", courses=course_cards())


@web.route("/courses/<int:course_id>", methods=["GET", "POST"])
def course_detail(course_id):
    course = course_record(course_id)
    if request.method == "POST":
        try:
            raw = request.form.get("score", "").strip()
            assignment = Assignment(
                request.form.get("title"),
                request.form.get("due"),
                request.form.get("weight"),
                request.form.get("minutes"),
                None if raw == "" else raw,
            )
            # Serialize the weight check and insert so concurrent forms cannot exceed 100%.
            with storage.db():
                storage.db().execute("BEGIN IMMEDIATE")
                items = storage.rows(
                    "SELECT * FROM assignments WHERE course_id=?", (course_id,)
                )
                if (
                    assignment.weight
                    > Course(course["title"], course["target"]).remaining_weight(items)
                    + 1e-6
                ):
                    raise ValueError(
                        "Assignment weights cannot add up to more than 100%."
                    )
                storage.db().execute(
                    """INSERT INTO assignments(course_id,title,due,weight,minutes,score,completed)
                   VALUES (?,?,?,?,?,?,?)""",
                    (
                        course_id,
                        assignment.title,
                        assignment.due,
                        assignment.weight,
                        assignment.minutes,
                        assignment.score,
                        int(assignment.score is not None),
                    ),
                )
            flash("Assignment added.", "success")
        except ValueError as error:
            flash(str(error), "error")
        return redirect(url_for("web.course_detail", course_id=course_id))
    assignments = storage.rows(
        "SELECT * FROM assignments WHERE course_id=? ORDER BY due,id", (course_id,)
    )
    summary, _ = calculate("grade", {"items": assignments})
    return render_template(
        "course.html",
        course=course,
        assignments=assignments,
        summary=summary,
        goal=target_progress(summary, course["target"]),
        lecture_count=storage.rows(
            "SELECT COUNT(*) AS n FROM lectures WHERE course_id=?", (course_id,)
        )[0]["n"],
        remaining=Course(course["title"], course["target"]).remaining_weight(
            assignments
        ),
    )


@web.post("/assignments/<int:assignment_id>/update")
def update_assignment(assignment_id):
    record = storage.rows("SELECT * FROM assignments WHERE id=?", (assignment_id,))
    if not record:
        abort(404)
    try:
        raw = request.form.get("score", "").strip()
        score = None if raw == "" else number(raw, "Score", 0, 100)
        completed = request.form.get("completed") == "yes" or score is not None
        with storage.db():
            storage.db().execute(
                "UPDATE assignments SET score=?,completed=? WHERE id=?",
                (score, int(completed), assignment_id),
            )
        flash("Assignment updated.", "success")
    except ValueError as error:
        flash(str(error), "error")
    return redirect(url_for("web.course_detail", course_id=record[0]["course_id"]))


@web.post("/assignments/<int:assignment_id>/delete")
def delete_assignment(assignment_id):
    record = storage.rows("SELECT * FROM assignments WHERE id=?", (assignment_id,))
    if not record:
        abort(404)
    with storage.db():
        storage.db().execute("DELETE FROM assignments WHERE id=?", (assignment_id,))
    flash("Assignment deleted.", "success")
    return redirect(url_for("web.course_detail", course_id=record[0]["course_id"]))


@web.route("/study", methods=["GET", "POST"])
def study():
    plan = None
    explanation = None
    mode = "Rule-based plan"
    available = 120
    content = ""
    unused = 0
    if request.method == "POST":
        try:
            minutes = number(
                request.form.get("available"), "Available minutes", 1, 1440
            )
            if not minutes.is_integer():
                raise ValueError("Available minutes must be a whole number.")
            available = int(minutes)
            tasks = storage.open_tasks()
            result, _ = calculate("plan", {"tasks": tasks, "available": available})
            by_id = {task["id"]: task for task in tasks}
            plan = [
                {**by_id[item["id"]], "allocated": item["minutes"]}
                for item in result["sessions"]
            ]
            if request.form.get("use_ai") == "yes" and plan:
                try:
                    explanation = ai.explain(
                        [
                            {
                                "task": item["title"],
                                "course": item["course"],
                                "due": item["due"],
                                "minutes": item["allocated"],
                            }
                            for item in plan
                        ]
                    )
                    mode = "AI-assisted plan"
                except ValueError as error:
                    flash(str(error), "error")
            if plan:
                content = "\n".join(
                    f"{item['course']} / {item['title']}: {item['allocated']} minutes (due {item['due']})"
                    for item in plan
                )
                if explanation:
                    content += "\n\nAI suggestions (review before use):\n" + explanation
                unused = result["unused_minutes"]
        except ValueError as error:
            flash(str(error), "error")
    return render_template(
        "study.html",
        plan=plan,
        content=content,
        explanation=explanation,
        mode=mode,
        available=available,
        unused=unused,
        saved=storage.rows("SELECT * FROM plans ORDER BY id DESC LIMIT 5"),
    )


@web.post("/study/save")
def save_plan():
    content = request.form.get("content", "").strip()
    if not content or len(content) > 12000:
        flash("A plan must contain 1–12,000 characters.", "error")
    else:
        with storage.db():
            storage.db().execute(
                "INSERT INTO plans(content,mode) VALUES (?,?)",
                (content, "Reviewed by student"),
            )
        flash("Your reviewed plan is saved.", "success")
    return redirect(url_for("web.study"))


@web.post("/demo")
def demo():
    with storage.db():
        storage.db().execute("BEGIN IMMEDIATE")
        if storage.rows("SELECT id FROM courses LIMIT 1"):
            flash("Sample data is available only in an empty workspace.", "error")
            return redirect(url_for("web.dashboard"))
        storage.db().executemany(
            "INSERT INTO courses(title,target) VALUES (?,?)",
            [("CMPSC 460", 90), ("MATH 140", 85), ("ENGL 15", 90)],
        )
        ids = {c["title"]: c["id"] for c in storage.rows("SELECT * FROM courses")}
        today = date.today()
        fixture = [
            (ids["CMPSC 460"], "Homework 1", -7, 20, 45, 80, 1),
            (ids["CMPSC 460"], "Paradigm prototypes", 2, 30, 90, None, 0),
            (ids["CMPSC 460"], "Final application", 14, 50, 180, None, 0),
            (ids["MATH 140"], "Quiz 1", -5, 20, 30, 92, 1),
            (ids["MATH 140"], "Problem set 3", 1, 20, 60, None, 0),
            (ids["ENGL 15"], "Essay outline", 4, 25, 45, None, 0),
        ]
        storage.db().executemany(
            """INSERT INTO assignments(course_id,title,due,weight,minutes,score,completed)
            VALUES (?,?,?,?,?,?,?)""",
            [
                (c, t, (today + timedelta(days=d)).isoformat(), w, m, s, done)
                for c, t, d, w, m, s, done in fixture
            ],
        )
    flash(
        "Fictional sample courses added. You can change their scores or add your own.",
        "success",
    )
    return redirect(url_for("web.dashboard"))
