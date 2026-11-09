# Implementation guide

## Architecture

The browser submits a form to Flask. Flask verifies the request token and validates fields. Python `Course` and `Assignment` objects enforce domain rules. SQLite stores the accepted data. Flask retrieves records with parameterized SQL, sends JSON to the fixed Racket runner and renders the result. The study planner optionally sends only its selected schedule to the AI adapter. The student explicitly saves a reviewed plan.

`racket_bridge.py` invokes a fixed executable/script pair, with no shell and no evaluation of submitted code. The runner translates JSON into data structures matching the two DSL grammars. A timeout or rejected input becomes a visible error. Racket is the active calculation engine in the tested local preview.

## Where the four paradigms work

**Imperative:** `studytrack/routes.py` contains ordered request workflows. For example, `course_detail` reads fields, creates an assignment, checks the total weight inside a transaction, writes to SQLite, and redirects. The standalone proof is `prototypes/imperative.py`, with explicit validation, loops and accumulated totals. It requires a complete course with 100% weight.

**Object-oriented:** `studytrack/domain.py` defines immutable `Course` and `Assignment` objects. Their constructors enforce valid names, dates, scores, weights and durations. `Course.remaining_weight` owns a course-specific rule used by the application. `prototypes/object_oriented.py` adds a `Gradebook` that encapsulates its assignments and exposes methods. The app and prototype share the domain objects. Object immutability does not prevent object-oriented responsibilities.

**Functional:** `racket/DSL_1.rkt` uses `map` and `filter` over immutable lists to calculate graded progress. `DSL_2.rkt` recursively constructs a study schedule without mutation. Both run in the application through `racket/runner.rkt`. `studytrack/functional.py` provides equivalent pure transformations for environments without Racket. These calculations return new values and have no I/O. Subprocess I/O is isolated in the bridge.

**Declarative:** `studytrack/storage.py` defines relational tables and SQL filtering. `UPCOMING_SQL` declares open assignments in an inclusive date window, joining course names and ordering by due date. SQLite determines how to execute it. `prototypes/declarative.sql` supplies an isolated, repeatable example. A separate query retrieves overdue assignments, so they remain visible.

## Two DSLs

`DSL_1.rkt` accepts `(course (item score weight) ...)`. Weights use percentages. `#f` means ungraded. Example: `(course (item 80 40) (item 90 60))` returns a current grade of 86.0. It accepts incomplete course definitions but rejects totals above 100%. Empty input returns an unknown current grade, not zero. It also returns graded weight and final-grade points earned.

`DSL_2.rkt` accepts `(study-plan (available minutes) (task id minutes) ...)`. Example: `(study-plan (available 120) (task 1 60) (task 2 90))` allocates 60 minutes to each task and leaves no unused time. Task order is meaningful. SQL provides deadline order before interpretation. Task IDs are unique positive integers. Unknown forms and invalid durations fail. These are restricted interpreters, not general Racket evaluators.

Both files have `module+ main` examples and `module+ test` RackUnit checks. Open either in DrRacket and Run to see its example. Use `raco test` to execute the tests.

## Prototype comparison

The imperative prototype makes control flow explicit and easy to trace, but larger mutable workflows are more sensitive to execution order. The OOP prototype organizes state around a course and encapsulates its rules, at the cost of more structure. The functional prototype makes transformations repeatable and easy to test, but I/O needs a separate boundary. The declarative prototype expresses retrieval concisely and delegates execution to SQL, while workflow and explanatory text remain in other layers.

The three grade prototypes share the 86% fixture. The declarative prototype solves the related deadline-selection part of the same student-progress problem. Compare identical complete-grade inputs for the first three; the application additionally supports partial grading.

## Research continuity

The final November 8 SLR retains Deloitte Tech Trends 2026 and uses four verified official reports: Google Cloud/DORA 2025, Microsoft Work Trend Index 2025, Stack Overflow Developer Survey 2025, and GitHub Octoverse 2025. The final report documents the method and why the earlier general articles and author-hosted manuscript were replaced. Earlier presentations remain historical drafts; the final report is the current research record.

## Technical references

- Flask quickstart: https://flask.palletsprojects.com/en/stable/quickstart/
- Racket guide: https://docs.racket-lang.org/guide/
- OpenAI text generation: https://developers.openai.com/api/docs/guides/text

## Demonstration sequence

Start with fictional sample courses. Open CMPSC 460, change Homework 1 from 80 to 85, save and show recalculation. Restore 80. Open the study planner with 120 minutes. Show two 60-minute allocations and save the reviewed plan. Then run the four standalone prototypes and the tests. Point to each component above. Demonstrate real AI only after configuring it and recording a successful, human-reviewed response.

## Lecture-driven study workflow (October 2026)

The course page now connects target-grade arithmetic to a lecture library and study-guide builder. `materials.py` extracts bounded, source-labeled text from PDF/PPTX/DOCX/TXT/Markdown in a short-lived parser process. `guidance.py` computes the remaining weighted average, selects passages, and builds timed recall/practice sessions. `learning.py` coordinates forms and SQLite persistence. The original grade and allocation DSLs remain integrated through `racket_bridge.py`.

The database adds `lectures` and `study_guides` without replacing courses, assignments, or plans. Guides retain source snapshots and distinguish generated content from student-reviewed text. The optional AI adapter validates source IDs and verbatim evidence before accepting explanations. This validates attribution, not the truth of every AI claim; students still review the result. Local guides work without credentials. Live API behavior remains unverified without configured credentials.

The target affects the practice-time share, not a promised grade. Passage selection is keyword-based, limited to six passages, and does not claim full lecture coverage. This build has source-based recall checks, not a comprehensive quiz engine or conversational tutor.
