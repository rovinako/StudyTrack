"""Lecture library and course-specific study guides."""

import json
from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
    Response,
)
from . import ai, storage
from .domain import Course, name, number
from .routes import course_record
from .racket_bridge import calculate
from .materials import read_upload
from .guidance import make_guide, guide_text, target_progress

learning = Blueprint("learning", __name__)


def course_context(course_id):
    course = course_record(course_id)
    assignments = storage.rows(
        "SELECT * FROM assignments WHERE course_id=? ORDER BY due,id", (course_id,)
    )
    summary, _ = calculate("grade", {"items": assignments})
    return course, assignments, summary


def lecture_records(course_id):
    records = storage.rows(
        "SELECT * FROM lectures WHERE course_id=? ORDER BY id DESC", (course_id,)
    )
    for record in records:
        record["sections"] = json.loads(record["sections_json"])
    return records


@learning.post("/courses/<int:course_id>/target")
def update_target(course_id):
    course = course_record(course_id)
    try:
        validated = Course(course["title"], request.form.get("target"))
        with storage.db():
            storage.db().execute(
                "UPDATE courses SET target=? WHERE id=?", (validated.target, course_id)
            )
        flash("Target grade updated. Your next guide will use this goal.", "success")
    except ValueError as error:
        flash(str(error), "error")
    return redirect(url_for("web.course_detail", course_id=course_id))


@learning.route("/materials", methods=["GET"])
def library():
    courses = storage.rows(
        "SELECT c.*,COUNT(l.id) AS lecture_count FROM courses c LEFT JOIN lectures l ON l.course_id=c.id GROUP BY c.id ORDER BY c.title"
    )
    return render_template("library.html", courses=courses)


@learning.route("/courses/<int:course_id>/materials", methods=["GET", "POST"])
def materials(course_id):
    course = course_record(course_id)
    if request.method == "POST":
        try:
            upload = request.files.get("lecture")
            if upload is None or not upload.filename:
                raise ValueError("Choose a lecture file first.")
            filename, sections = read_upload(upload)
            title = name(request.form.get("title") or filename, "Lecture title", 180)
            size = sum(len(s["text"]) for s in sections)
            with storage.db():
                storage.db().execute("BEGIN IMMEDIATE")
                totals = storage.rows(
                    "SELECT COUNT(*) AS count, COALESCE(SUM(characters),0) AS chars FROM lectures WHERE course_id=?",
                    (course_id,),
                )[0]
                if totals["count"] >= 20 or totals["chars"] + size > 600_000:
                    raise ValueError(
                        "This course has reached its lecture limit (20 files / 600,000 characters). Remove an old lecture first."
                    )
                cursor = storage.db().execute(
                    "INSERT INTO lectures(course_id,title,filename,sections_json,characters) VALUES (?,?,?,?,?)",
                    (course_id, title, filename, json.dumps(sections), size),
                )
            flash(
                "Lecture uploaded. Check the extracted text, then build your study guide.",
                "success",
            )
            return redirect(url_for("learning.lecture", lecture_id=cursor.lastrowid))
        except ValueError as error:
            flash(str(error), "error")
        return redirect(url_for("learning.materials", course_id=course_id))
    return render_template(
        "materials.html", course=course, lectures=lecture_records(course_id)
    )


@learning.get("/lectures/<int:lecture_id>")
def lecture(lecture_id):
    result = storage.rows("SELECT * FROM lectures WHERE id=?", (lecture_id,))
    if not result:
        abort(404)
    record = result[0]
    record["sections"] = json.loads(record["sections_json"])
    return render_template(
        "lecture.html",
        lecture=record,
        course=course_record(record["course_id"]),
        existing_lectures={
            l["id"]
            for l in storage.rows(
                "SELECT id FROM lectures WHERE course_id=?", (record["course_id"],)
            )
        },
    )


@learning.post("/lectures/<int:lecture_id>/delete")
def delete_lecture(lecture_id):
    records = storage.rows("SELECT * FROM lectures WHERE id=?", (lecture_id,))
    if not records:
        abort(404)
    with storage.db():
        storage.db().execute("DELETE FROM lectures WHERE id=?", (lecture_id,))
    flash(
        "Lecture removed. Existing guides keep the source excerpts they were created with.",
        "success",
    )
    return redirect(url_for("learning.materials", course_id=records[0]["course_id"]))


@learning.route("/courses/<int:course_id>/guide", methods=["GET", "POST"])
def create_guide(course_id):
    course, assignments, summary = course_context(course_id)
    lectures = lecture_records(course_id)
    values = {
        "available": "60",
        "focus": "",
        "assignment_id": "",
        "lecture_ids": [str(l["id"]) for l in lectures],
        "use_ai": False,
    }
    if request.method == "POST":
        values = {
            "available": request.form.get("available", ""),
            "focus": request.form.get("focus", "").strip(),
            "assignment_id": request.form.get("assignment_id", ""),
            "lecture_ids": request.form.getlist("lecture_ids"),
            "use_ai": request.form.get("use_ai") == "yes",
        }
        try:
            if len(values["focus"]) > 180:
                raise ValueError("Keep the focus topic to 180 characters or fewer.")
            allowed = {str(l["id"]): l for l in lectures}
            if not values["lecture_ids"] or any(
                i not in allowed for i in values["lecture_ids"]
            ):
                raise ValueError("Select at least one lecture from this course.")
            selected = [allowed[i] for i in dict.fromkeys(values["lecture_ids"])]
            assessment = None
            if values["assignment_id"]:
                assessment = next(
                    (
                        a
                        for a in assignments
                        if str(a["id"]) == values["assignment_id"]
                        and a["score"] is None
                    ),
                    None,
                )
                if assessment is None:
                    raise ValueError("Choose an ungraded assessment from this course.")
            guide = make_guide(
                course,
                summary,
                selected,
                values["available"],
                values["focus"],
                assessment,
            )
            if values["use_ai"]:
                try:
                    guide["ai_sections"] = ai.lecture_coach(guide)
                    guide["mode"] = "AI-assisted lecture guide"
                except ValueError as error:
                    flash(
                        str(error) + " Your lecture-based guide is still available.",
                        "error",
                    )
            with storage.db():
                cursor = storage.db().execute(
                    "INSERT INTO study_guides(course_id,content_json) VALUES (?,?)",
                    (course_id, json.dumps(guide)),
                )
            return redirect(url_for("learning.view_guide", guide_id=cursor.lastrowid))
        except ValueError as error:
            flash(str(error), "error")
    return render_template(
        "guide_form.html",
        course=course,
        assignments=assignments,
        goal=target_progress(summary, course["target"]),
        lectures=lectures,
        values=values,
        history=storage.rows(
            "SELECT id,created,reviewed_text FROM study_guides WHERE course_id=? ORDER BY id DESC LIMIT 10",
            (course_id,),
        ),
    )


def guide_record(guide_id):
    records = storage.rows("SELECT * FROM study_guides WHERE id=?", (guide_id,))
    if not records:
        abort(404)
    return records[0]


@learning.route("/guides/<int:guide_id>", methods=["GET", "POST"])
def view_guide(guide_id):
    record = guide_record(guide_id)
    guide = json.loads(record["content_json"])
    text = (
        record["reviewed_text"]
        if record["reviewed_text"] is not None
        else guide_text(guide)
    )
    if request.method == "POST":
        text = request.form.get("content", "").strip()
        if not 1 <= len(text) <= 24000:
            flash("A reviewed guide must contain 1–24,000 characters.", "error")
        else:
            with storage.db():
                storage.db().execute(
                    "UPDATE study_guides SET reviewed_text=? WHERE id=?",
                    (text, guide_id),
                )
            flash("Your reviewed study guide is saved.", "success")
            return redirect(url_for("learning.view_guide", guide_id=guide_id))
    return render_template(
        "guide.html",
        record=record,
        guide=guide,
        content=text,
        course=course_record(record["course_id"]),
        existing_lectures={
            l["id"]
            for l in storage.rows(
                "SELECT id FROM lectures WHERE course_id=?", (record["course_id"],)
            )
        },
    )


@learning.get("/guides/<int:guide_id>/download")
def download_guide(guide_id):
    record = guide_record(guide_id)
    if record["reviewed_text"] is None:
        abort(400, description="Review and save this guide before downloading it.")
    return Response(
        record["reviewed_text"],
        mimetype="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="studytrack-guide-{guide_id}.txt"'
        },
    )


@learning.post("/guides/<int:guide_id>/delete")
def delete_guide(guide_id):
    record = guide_record(guide_id)
    with storage.db():
        storage.db().execute("DELETE FROM study_guides WHERE id=?", (guide_id,))
    flash("Study guide deleted.", "success")
    return redirect(url_for("learning.create_guide", course_id=record["course_id"]))
