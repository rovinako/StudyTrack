import copy
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from studytrack import create_app, ai, storage
from studytrack.domain import Assignment, Course
from studytrack.functional import grade_summary, allocate
from studytrack.racket_bridge import calculate, executable
from prototypes.imperative import weighted_grade
from prototypes.object_oriented import Gradebook


class Calculations(unittest.TestCase):
    def setUp(self):
        self.items = [{"score": 80, "weight": 40}, {"score": 90, "weight": 60}]

    def test_shared_grade_fixture(self):
        self.assertEqual(weighted_grade([(80, 40), (90, 60)]), 86)
        self.assertEqual(grade_summary(self.items)["current"], 86)
        book = Gradebook(Course("Test"))
        book.add(Assignment("A", "2026-04-20", 40, 60, 80))
        book.add(Assignment("B", "2026-04-22", 60, 90, 90))
        self.assertEqual(book.current_grade(), 86)
        self.assertIsNone(Gradebook(Course("Independent")).current_grade())

    def test_pure_repeatable_and_unchanged(self):
        original = copy.deepcopy(self.items)
        self.assertEqual(grade_summary(self.items), grade_summary(self.items))
        self.assertEqual(self.items, original)

    def test_zero_missing_and_empty(self):
        self.assertIsNone(grade_summary([])["current"])
        self.assertEqual(
            grade_summary([{"score": 0, "weight": 40}, {"score": None, "weight": 60}])[
                "current"
            ],
            0,
        )
        self.assertEqual(
            grade_summary([{"score": 80, "weight": 40}, {"score": None, "weight": 60}])[
                "current"
            ],
            80,
        )

    def test_invalid_inputs(self):
        for value in [-1, 101, float("nan"), float("inf")]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                Assignment("A", "2026-04-20", 40, 60, value)
        with self.assertRaises(ValueError):
            Assignment("A", "bad", 40, 60)
        with self.assertRaises(ValueError):
            grade_summary([{"score": 80, "weight": 70}, {"score": 90, "weight": 60}])
        with self.assertRaises(ValueError):
            allocate([{"id": 1, "minutes": 60}, {"id": 1, "minutes": 60}], 120)
        with self.assertRaises(ValueError):
            allocate([], -1)

    def test_schedule_budget(self):
        tasks = [{"id": 1, "minutes": 60}, {"id": 2, "minutes": 90}]
        original = copy.deepcopy(tasks)
        self.assertEqual(
            allocate(tasks, 120),
            {
                "sessions": [{"id": 1, "minutes": 60}, {"id": 2, "minutes": 60}],
                "unused_minutes": 0,
            },
        )
        self.assertEqual(allocate([], 120)["unused_minutes"], 120)
        self.assertEqual(allocate(tasks, 0)["sessions"], [])
        self.assertEqual(tasks, original)

    @unittest.skipUnless(executable(), "Racket runtime not configured")
    def test_real_racket_parity(self):
        for items in [
            self.items,
            [],
            [{"score": 0, "weight": 40}, {"score": None, "weight": 60}],
        ]:
            result, engine = calculate("grade", {"items": items})
            self.assertEqual(engine, "Racket DSL")
            self.assertEqual(result, grade_summary(items))
        tasks = [{"id": 1, "minutes": 60}, {"id": 2, "minutes": 90}]
        self.assertEqual(
            calculate("plan", {"tasks": tasks, "available": 120})[0],
            allocate(tasks, 120),
        )
        with self.assertRaises(ValueError):
            calculate("grade", {"items": [{"score": 200, "weight": 40}]})

    def test_racket_timeout(self):
        import subprocess

        with patch("studytrack.racket_bridge.executable", return_value="racket"), patch(
            "studytrack.racket_bridge.subprocess.run",
            side_effect=subprocess.TimeoutExpired("racket", 8),
        ):
            with self.assertRaises(ValueError):
                calculate("grade", {"items": self.items})

    def test_declarative_prototype(self):
        from contextlib import closing

        with closing(sqlite3.connect(":memory:")) as db:
            db.executescript(Path("prototypes/declarative.sql").read_text())
            self.assertEqual(
                db.execute(
                    "SELECT title FROM tasks WHERE completed=0 AND due BETWEEN '2026-04-18' AND '2026-04-25'"
                ).fetchall(),
                [("A",)],
            )


class WebWorkflow(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "test.sqlite")
        self.app = create_app(
            {"TESTING": True, "SECRET_KEY": "test-only", "DATABASE": self.path}
        )
        self.client = self.app.test_client()
        self.client.get("/")
        with self.client.session_transaction() as session:
            self.csrf = session["csrf"]

    def tearDown(self):
        self.temp.cleanup()

    def post(self, path, data=None):
        return self.client.post(
            path, data={"csrf": self.csrf, **(data or {})}, follow_redirects=True
        )

    def add(self, **overrides):
        return self.post(
            "/courses/1",
            {
                "title": "Homework",
                "due": "2026-04-20",
                "weight": "40",
                "minutes": "60",
                "score": "80",
                **overrides,
            },
        )

    def test_complete_saved_workflow(self):
        self.post("/courses", {"title": "CMPSC 460", "target": "90"})
        self.add()
        self.assertIn(b"86.0%", self.add(title="Exam", weight="60", score="90").data)
        self.post("/assignments/2/update", {"score": "", "completed": ""})
        response = self.post("/study", {"available": "120"})
        self.assertIn(b"Exam", response.data)
        self.assertIn(b"Rule-based plan", response.data)
        self.assertIn(
            b"My reviewed plan",
            self.post("/study/save", {"content": "My reviewed plan"}).data,
        )
        other = create_app({"TESTING": True, "DATABASE": self.path})
        self.assertIn(b"CMPSC 460", other.test_client().get("/").data)

    def test_validation_and_weight_transaction(self):
        self.post("/courses", {"title": "Test", "target": "90"})
        self.add(weight="70")
        self.assertIn(b"cannot add up", self.add(title="Too much").data)
        self.assertIn(b"Score must be", self.add(score="nan", weight="10").data)
        with self.app.app_context():
            self.assertEqual(len(storage.rows("SELECT * FROM assignments")), 1)
        self.assertIn(
            b"already exists",
            self.post("/courses", {"title": "Test", "target": "90"}).data,
        )

    def test_csrf_and_escape(self):
        self.assertEqual(
            self.client.post(
                "/courses", data={"title": "bad", "target": "90"}
            ).status_code,
            400,
        )
        self.assertIn(
            b"&lt;script&gt;",
            self.post("/courses", {"title": "<script>", "target": "90"}).data,
        )
        self.assertEqual(self.client.get("/courses/999").status_code, 404)

    def test_delete(self):
        self.post("/courses", {"title": "Test", "target": "90"})
        self.add()
        self.post("/assignments/1/delete")
        with self.app.app_context():
            self.assertEqual(storage.rows("SELECT * FROM assignments"), [])

    def test_sql_boundaries(self):
        self.post("/courses", {"title": "Test", "target": "90"})
        for title, due in [
            ("start", "2026-04-18"),
            ("end", "2026-04-25"),
            ("late", "2026-04-26"),
        ]:
            self.add(title=title, due=due, weight="20", score="")
        self.add(title="finished", due="2026-04-20", weight="20", score="80")
        with self.app.app_context():
            self.assertEqual(
                [x["title"] for x in storage.due_tasks("2026-04-18", "2026-04-25")],
                ["start", "end"],
            )

    def test_empty_planner_and_demo_protection(self):
        self.assertIn(
            b"No open assignments", self.post("/study", {"available": "120"}).data
        )
        self.assertIn(b"whole number", self.post("/study", {"available": "1.5"}).data)
        self.post("/demo")
        self.assertIn(b"only in an empty workspace", self.post("/demo").data)
        with self.app.app_context():
            self.assertEqual(len(storage.rows("SELECT * FROM courses")), 3)


class AIAdapter(unittest.TestCase):
    def test_unconfigured(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(ai.configured())
            with self.assertRaises(ValueError):
                ai.explain([])

    def test_response_and_privacy(self):
        fake = {
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "Review your notes."}],
                }
            ],
        }
        with patch.dict(
            os.environ, {"OPENAI_API_KEY": "test", "OPENAI_MODEL": "test-model"}
        ), patch(
            "studytrack.ai.urlopen", return_value=io.BytesIO(json.dumps(fake).encode())
        ) as call:
            self.assertEqual(
                ai.explain([{"task": "A", "minutes": 60}]), "Review your notes."
            )
            self.assertFalse(json.loads(call.call_args.args[0].data)["store"])

    def test_malformed_response(self):
        with patch.dict(
            os.environ, {"OPENAI_API_KEY": "test", "OPENAI_MODEL": "test-model"}
        ), patch("studytrack.ai.urlopen", return_value=io.BytesIO(b"[]")):
            with self.assertRaisesRegex(ValueError, "unavailable"):
                ai.explain([])

    def test_failure(self):
        from urllib.error import URLError

        with patch.dict(
            os.environ, {"OPENAI_API_KEY": "test", "OPENAI_MODEL": "test-model"}
        ), patch("studytrack.ai.urlopen", side_effect=URLError("offline")):
            with self.assertRaisesRegex(ValueError, "unavailable"):
                ai.explain([])


if __name__ == "__main__":
    unittest.main()
