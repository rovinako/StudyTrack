import io
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch
from werkzeug.datastructures import FileStorage
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from studytrack import create_app, storage, ai
from studytrack.functional import grade_summary
from studytrack.guidance import (
    target_progress,
    make_guide,
    choose_sources,
    recall_question,
)
from studytrack.materials import read_upload, MAX_BYTES

LECTURE = """Functional programming
Pure functions return the same output for the same input and do not mutate external state.
Immutability means keeping existing data unchanged and creating new values instead.
Recursion solves a problem by calling the same function on a smaller input. A base case stops recursion.
Map applies a transformation to each element. Filter keeps the elements that satisfy a predicate.
"""


def document(extension):
    stream = io.BytesIO()
    if extension == "pdf":
        writer = PdfWriter()
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {NameObject("/F1"): writer._add_object(font)}
                )
            }
        )
        content = DecodedStreamObject()
        content.set_data(
            b"BT /F1 12 Tf 40 700 Td (Pure functions return the same result and do not mutate external state.) Tj ET"
        )
        page[NameObject("/Contents")] = writer._add_object(content)
        writer.write(stream)
    else:
        with ZipFile(stream, "w") as z:
            if extension == "docx":
                z.writestr(
                    "word/document.xml",
                    f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>{LECTURE}</w:t></w:r></w:p></w:body></w:document>',
                )
            else:
                z.writestr(
                    "ppt/presentation.xml",
                    '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst><p:sldId id="1" r:id="r2"/><p:sldId id="2" r:id="r1"/></p:sldIdLst></p:presentation>',
                )
                z.writestr(
                    "ppt/_rels/presentation.xml.rels",
                    '<Relationships><Relationship Id="r1" Target="slides/slide1.xml"/><Relationship Id="r2" Target="slides/slide2.xml"/></Relationships>',
                )
                for i in [1, 2]:
                    z.writestr(
                        f"ppt/slides/slide{i}.xml",
                        f'<slide><a:p xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:r><a:t>Slide file {i}. {LECTURE}</a:t></a:r></a:p></slide>',
                    )
    return stream.getvalue()


class GoalsAndGuides(unittest.TestCase):
    def test_recall_prefers_topic_over_document_boilerplate(self):
        source = {
            "text": "Pure functions\nSample lecture for trying StudyTrack, not an official course handout.\nA pure function always returns the same output for the same input.",
            "location": "Slide 1",
        }
        result = recall_question(source)
        self.assertIn("pure function", result["evidence"])
        self.assertNotEqual(result["answer"], "StudyTrack")

    def setUp(self):
        self.summary = grade_summary(
            [{"score": 80, "weight": 20}, {"score": None, "weight": 80}]
        )
        self.lectures = [
            {
                "id": 1,
                "title": "Functional programming",
                "sections": [{"location": "Slide 1", "text": LECTURE}],
            }
        ]

    def test_required_average_not_current_grade(self):
        goal = target_progress(self.summary, 90)
        self.assertAlmostEqual(goal["required"], 92.5)
        self.assertEqual(goal["maximum"], 96)
        self.assertEqual(goal["missing"], 0)
        self.assertEqual(target_progress(self.summary, 99)["status"], "unreachable")

    def test_empty_zero_complete_partial(self):
        self.assertEqual(target_progress(grade_summary([]), 90)["required"], 90)
        self.assertEqual(
            target_progress(grade_summary([{"score": 0, "weight": 50}]), 90)["status"],
            "unreachable",
        )
        full = target_progress(grade_summary([{"score": 85, "weight": 100}]), 90)
        self.assertIsNone(full["required"])
        self.assertEqual(full["status"], "complete")
        self.assertEqual(target_progress(self.summary, 0)["status"], "secured")
        self.assertEqual(
            target_progress(grade_summary([{"score": 80, "weight": 20}]), 90)[
                "missing"
            ],
            80,
        )
        for bad in ["nan", 101, -1]:
            with self.assertRaises(ValueError):
                target_progress(self.summary, bad)

    def test_budget_and_target_influence(self):
        low = make_guide(
            {"title": "Test", "target": 75}, self.summary, self.lectures, 60
        )
        high = make_guide(
            {"title": "Test", "target": 90}, self.summary, self.lectures, 60
        )
        self.assertGreater(
            high["sessions"][0]["practice"], low["sessions"][0]["practice"]
        )
        for total in [10, 31, 60, 480]:
            guide = make_guide(
                {"title": "Test", "target": 90}, self.summary, self.lectures, total
            )
            self.assertEqual(sum(s["minutes"] for s in guide["sessions"]), total)
            for s in guide["sessions"]:
                self.assertEqual(s["read"] + s["practice"] + s["check"], s["minutes"])
                self.assertGreater(s["read"], 0)
                self.assertIn(s["question"]["answer"], s["source"]["text"])
        with self.assertRaises(ValueError):
            make_guide(
                {"title": "Test", "target": 90}, self.summary, self.lectures, 10.5
            )

    def test_focus_and_source_selection(self):
        self.assertEqual(choose_sources(self.lectures, "recursion")[0]["id"], "L1-1")
        with self.assertRaisesRegex(ValueError, "not found"):
            choose_sources(self.lectures, "photosynthesis")
        other = {
            "id": 2,
            "title": "Other",
            "sections": [
                {
                    "location": "Text",
                    "text": "Cellular respiration releases energy from sugars inside cells.",
                }
            ],
        }
        self.assertEqual(
            [
                r["lecture_id"]
                for r in choose_sources(self.lectures + [other], "respiration")
            ],
            [2],
        )


class Uploads(unittest.TestCase):
    def test_formats_and_presentation_order(self):
        for ext in ["pdf", "pptx", "docx"]:
            with self.subTest(ext=ext):
                _, sections = read_upload(
                    FileStorage(
                        stream=io.BytesIO(document(ext)), filename="lecture." + ext
                    )
                )
                self.assertTrue(sections)
                self.assertIn("Pure functions", " ".join(s["text"] for s in sections))
                if ext == "pptx":
                    self.assertEqual(sections[0]["location"], "Slide 1")
                    self.assertIn("Slide file 2", sections[0]["text"])
        for ext in ["txt", "md"]:
            name, parts = read_upload(
                FileStorage(
                    stream=io.BytesIO(LECTURE.encode()), filename="../../lecture." + ext
                )
            )
            self.assertNotIn("/", name)
            self.assertIn("Recursion", parts[0]["text"])

    def test_invalid_empty_large_image_only(self):
        cases = [
            ("bad.exe", b"not a lecture"),
            ("bad.pdf", b"bad pdf"),
            ("blank.txt", b"  "),
            ("large.txt", b"a" * (MAX_BYTES + 1)),
            ("encoding.txt", b"\xff" * 100),
        ]
        blank = PdfWriter()
        blank.add_blank_page(width=612, height=792)
        stream = io.BytesIO()
        blank.write(stream)
        cases.append(("scan.pdf", stream.getvalue()))
        for filename, data in cases:
            with self.subTest(filename=filename), self.assertRaises(ValueError):
                read_upload(FileStorage(stream=io.BytesIO(data), filename=filename))

    def test_xml_entities_and_timeout(self):
        data = io.BytesIO()
        with ZipFile(data, "w") as z:
            z.writestr(
                "word/document.xml",
                '<!DOCTYPE x [<!ENTITY evil SYSTEM "file:///etc/passwd">]><x>&evil;</x>',
            )
        with self.assertRaises(ValueError):
            read_upload(
                FileStorage(stream=io.BytesIO(data.getvalue()), filename="bad.docx")
            )
        import subprocess

        with patch(
            "studytrack.materials.subprocess.run",
            side_effect=subprocess.TimeoutExpired("x", 20),
        ), self.assertRaises(ValueError):
            read_upload(
                FileStorage(stream=io.BytesIO(LECTURE.encode()), filename="notes.txt")
            )


class LearningWorkflow(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = str(Path(self.temp.name) / "test.sqlite")
        self.app = create_app(
            {"TESTING": True, "SECRET_KEY": "test", "DATABASE": self.database}
        )
        self.client = self.app.test_client()
        self.client.get("/")
        with self.client.session_transaction() as s:
            self.csrf = s["csrf"]
        self.post("/courses", {"title": "CMPSC 460", "target": 90})
        self.post(
            "/courses/1",
            {
                "title": "Quiz",
                "due": "2026-12-01",
                "weight": 20,
                "score": 80,
                "minutes": 30,
            },
        )
        self.post(
            "/courses/1",
            {
                "title": "Final exam",
                "due": "2026-12-15",
                "weight": 80,
                "score": "",
                "minutes": 120,
            },
        )

    def tearDown(self):
        self.temp.cleanup()

    def post(self, path, data=None):
        return self.client.post(
            path, data={"csrf": self.csrf, **(data or {})}, follow_redirects=True
        )

    def upload(self, course=1, content=LECTURE):
        return self.post(
            f"/courses/{course}/materials",
            {
                "title": "Week 4",
                "lecture": (io.BytesIO(content.encode()), "lecture.txt"),
            },
        )

    def test_upload_target_guide_review_download_restart(self):
        self.assertIn(b"Lecture uploaded", self.upload().data)
        self.assertIn(b"92.5%", self.client.get("/courses/1").data)
        self.assertIn(b"85.0%", self.post("/courses/1/target", {"target": 85}).data)
        response = self.post(
            "/courses/1/guide",
            {
                "available": 60,
                "lecture_ids": ["1"],
                "focus": "recursion",
                "assignment_id": "2",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Recall check", response.data)
        self.assertIn(b"Final exam", response.data)
        self.assertIn(b"86.2%", response.data)
        self.assertEqual(self.client.get("/guides/1/download").status_code, 400)
        self.assertIn(
            b"guide is saved",
            self.post(
                "/guides/1", {"content": "Reviewed guide with my own notes"}
            ).data,
        )
        self.assertEqual(
            self.client.get("/guides/1/download").data,
            b"Reviewed guide with my own notes",
        )
        other = create_app({"TESTING": True, "DATABASE": self.database})
        self.assertIn(
            b"Reviewed guide with my own notes",
            other.test_client().get("/guides/1").data,
        )
        self.post("/lectures/1/delete")
        self.assertIn(b"Pure functions", self.client.get("/guides/1").data)
        self.post("/guides/1/delete")
        self.assertEqual(self.client.get("/guides/1").status_code, 404)

    def test_invalid_cross_course_selection_and_escaping(self):
        self.upload(content=LECTURE + "\n<script>alert(1)</script>")
        self.assertIn(b"&lt;script&gt;", self.client.get("/lectures/1").data)
        self.post("/courses", {"title": "Other", "target": 90})
        self.upload(2)
        for data in [
            {"lecture_ids": ["2"], "available": 60},
            {"lecture_ids": ["1"], "available": 60, "focus": "photosynthesis"},
            {"lecture_ids": [], "available": 60},
            {"lecture_ids": ["1"], "available": "nan"},
            {"lecture_ids": ["1"], "available": 60, "assignment_id": 999},
        ]:
            response = self.post("/courses/1/guide", data)
            self.assertEqual(response.status_code, 200)
            with self.app.app_context():
                self.assertFalse(storage.rows("SELECT * FROM study_guides"))
        self.assertEqual(
            self.client.post(
                "/courses/1/materials",
                data={"lecture": (io.BytesIO(LECTURE.encode()), "a.txt")},
            ).status_code,
            400,
        )
        self.assertEqual(self.client.get("/lectures/999").status_code, 404)

    def test_ai_failure_keeps_guide_and_opt_in(self):
        self.upload()
        with patch("studytrack.ai.lecture_coach") as call:
            self.post("/courses/1/guide", {"lecture_ids": ["1"], "available": 60})
            call.assert_not_called()
        with patch(
            "studytrack.ai.lecture_coach", side_effect=ValueError("AI unavailable")
        ):
            response = self.post(
                "/courses/1/guide",
                {"lecture_ids": ["1"], "available": 60, "use_ai": "yes"},
            )
        self.assertIn(b"AI unavailable", response.data)
        self.assertIn(b"Pure functions", response.data)
        self.assertIn(b"Lecture-based guide", response.data)


class LectureAI(unittest.TestCase):
    def setUp(self):
        self.guide = make_guide(
            {"title": "Private course", "target": 90},
            grade_summary([{"score": 80, "weight": 20}]),
            [
                {
                    "id": 1,
                    "title": "Private lecture",
                    "sections": [{"location": "Text", "text": LECTURE}],
                }
            ],
            60,
        )
        self.section = {
            "source_id": "L1-1",
            "quote": "Pure functions return the same output for the same input",
            "explanation": "Pure functions are predictable.",
            "question": "What makes a function pure?",
            "answer": "Same input, same output without external mutation.",
        }

    def test_grounding_and_minimal_payload(self):
        with patch(
            "studytrack.ai._generate",
            return_value=json.dumps({"sections": [self.section]}),
        ) as call:
            self.assertEqual(ai.lecture_coach(self.guide), [self.section])
            data = call.call_args.args[0]
            self.assertEqual(data["target_percentage"], 90)
            self.assertNotIn("current", data)
            self.assertNotIn("Private course", json.dumps(data))
        for changed in [
            {"source_id": "L99-1"},
            {"quote": "This quote is invented"},
            {"answer": []},
            {"explanation": "x" * 701},
        ]:
            with patch(
                "studytrack.ai._generate",
                return_value=json.dumps({"sections": [{**self.section, **changed}]}),
            ), self.assertRaises(ValueError):
                ai.lecture_coach(self.guide)
        with patch(
            "studytrack.ai._generate", return_value="not json"
        ), self.assertRaises(ValueError):
            ai.lecture_coach(self.guide)
