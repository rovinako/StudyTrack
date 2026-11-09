# StudyTrack

**Rovena Nako · CMPSC 460 Programming Languages · Penn State Abington**

Stay on Track. Keep Improving.

StudyTrack is a local Flask web app for weighted grades, deadlines, uploaded lecture notes, and source-based study guides. This repository includes the complete application and final project materials.

## For the instructor

- [Final Word report and included paradigm audit](submission/StudyTrack_Final_Report.docx)
- [Company model paper](submission/StudyTrack_Company_Model_Paper.docx)
- [15-slide presentation](submission/StudyTrack_Final_Defense.pptx)
- [Architecture diagram](submission/Architecture_Diagram.png)
- [Four-paradigm integration matrix](submission/Four_Paradigm_Integration_Matrix.csv)
- [Four working prototypes](prototypes/)
- [Grade DSL](racket/DSL_1.rkt) and [study allocation DSL](racket/DSL_2.rkt)
- [Test and reproduction evidence](evidence/)
- [Application modules](studytrack/)

The source is available here publicly. The application runs locally at **http://127.0.0.1:5055** after setup; this repository is not a hosted live website.

**Verification status:** 33 Python tests and 16 Racket checks passed. Live AI provider verification is pending. The audit's 87/100 score is a provisional self-assessment, not an instructor grade or completed human approval.

## Application guide

StudyTrack helps a student track courses, weighted grades and deadlines, then create a study plan. This is a local, single-student class-project build. It does not yet include user accounts or public hosting.

## Start on this Mac

Double-click `start.command`, then open http://127.0.0.1:5055. The launcher uses the Python and Racket environments prepared for this workspace. Keep the terminal open while using the app. If another copy is already running, use the existing browser page.

The current preview contains fictional sample courses and one sample saved plan from testing. The downloadable source ZIP starts with an empty database. In an empty workspace, use **Try sample courses** to explore or add your own course.

## Run on another computer

Install Python 3.11 or newer and Racket (the full distribution includes DrRacket and RackUnit). In a terminal inside this folder:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Windows activation: `.venv\Scripts\activate`. Put `racket` on PATH or set `RACKET_BIN` to its executable. For Minimal Racket, install the test library with `raco pkg install --auto rackunit-lib`.

When Racket is available, the app calls both real Racket DSLs through a JSON bridge. Without Racket, the core app uses explicitly documented pure Python equivalents. The two `.rkt` deliverables still need Racket to run.

## Read the code in this order

1. `app.py` starts the server.
2. `studytrack/__init__.py` creates Flask and sets up shared request protection.
3. `studytrack/routes.py` contains the page workflows. Each route reads input, calls the relevant logic, and returns a page or redirect.
4. `studytrack/domain.py` defines Course and Assignment with their validation rules.
5. `studytrack/storage.py` contains SQLite setup and queries.
6. `studytrack/racket_bridge.py` connects Python to the two files in `racket/`. `functional.py` provides the offline Python equivalent.
7. `studytrack/ai.py` contains the optional AI connection.
8. `studytrack/templates/` contains the pages, and `studytrack/static/` contains their CSS and JavaScript.

Draft 2 separates routes from app setup, expands compressed Python/HTML/CSS/JavaScript, and gives the fallback calculations clearer names. The original audit sample in `docs/audit/` stays unchanged so the before/after evidence remains traceable.

## Try the app

1. Add a course and a target percentage.
2. Add assignments with due dates, a weight in the final grade, and estimated study minutes.
3. Leave scores empty until graded. Enter 0 for an actual zero. Entering a score also marks work complete.
4. Update scores or mark work complete in the course page. To reopen a scored assignment, clear its score and uncheck Completed.
5. Open Study planner and enter available minutes. It starts with the earliest unfinished deadlines, including overdue work.
6. Edit the generated plan if needed, then select **Save reviewed plan**. Reload to confirm persistence.

Weights are percentages, not fractions. For example, scores 80 and 90 with weights 40 and 60 produce 86%. If only the 80-point assignment is graded, the current grade is 80% on graded work and 32 final-grade points earned. The app does not invent a GPA scale or treat missing scores as zeros. A displayed target is a goal, not a prediction.

## Optional real AI connection

The app has a server-side OpenAI Responses API adapter. To enable it, export `OPENAI_API_KEY` and `OPENAI_MODEL` in the terminal before starting the app. Choose a model enabled for your API account. `.env.example` lists settings but does not load them automatically. Do not put keys in code, screenshots, the browser or your assignment submission.

The UI only sends course/task names, deadlines and allocated minutes when you check **Add AI study suggestions** and create a plan. This deadline-planner option does not send stored grades or lecture files. Generated study techniques remain suggestions that the student reviews. The deterministic schedule stays authoritative. The API request disables response storage using `store: false`; this is not a claim that the provider has no other retention.

No API key was available during this build. Adapter parsing and failure handling have automated mock tests, but a live AI response has **not** been tested. Until configured, the app says “AI is not connected” and labels its output “Rule-based plan.” This offline mode does not satisfy the final assignment's live AI requirement.

## Target-grade lecture workflow

1. Open a course, enter syllabus weights and scores, and update the target percentage.
2. Select **Upload lectures** and add PDF, PPTX, DOCX, TXT, or Markdown notes.
3. Select **Build a study guide**, choose lectures, available minutes, and an optional focus topic or upcoming assessment.
4. Read the cited passages, follow the read/practice/check time blocks, and try the recall questions before revealing answers.
5. Edit the guide, select **Save reviewed guide**, and download a text copy. Guides retain a snapshot; rebuild after updating grades or lectures.

For example, 80% on 20% of the course earns 16 final-grade points. A 90% target requires (90 − 16) / 80 × 100 = **92.5%** on the remaining weight. Missing syllabus weights are shown explicitly. Impossible targets are flagged rather than promised. A required average of at least 90% increases the practice share of the study budget from 35% to 50%; this is a transparent planning heuristic, not a validated grade predictor.

The local guide selects up to six passages by focus-word matches (or an overview across selected files), allocates minutes using the study DSL, and creates source-based fill-in-the-blank recall questions. It is not a comprehensive summary of every uploaded page. `examples/functional-programming-lecture.txt` is fictional material for a demonstration.

Optional **AI explanations and practice questions** sends only selected excerpts, source identifiers, the target percentage, focus, approach, and allocated minutes to the configured OpenAI model. It does not send the original files or full gradebook. Source IDs and quoted evidence are checked before displaying the response. Explanations can still be wrong and need student review. If AI fails, the local guide remains available. Live AI has not been tested because no API credentials were configured.

Uploads are limited to 10 MB, 150 PDF pages/slides, and 120,000 extracted characters per file. Each course supports 20 files and 600,000 extracted characters. Extraction runs in a separate process with a timeout and bounded document expansion. Original files are discarded; extracted text is stored in SQLite. Images, diagrams, formulas represented as images, and PowerPoint speaker notes are not extracted. Scanned documents need OCR first. Removing a lecture does not remove excerpts already captured in saved guides; remove those guides separately if needed.

New code is split by responsibility: `materials.py` extracts text, `guidance.py` calculates goals and builds guides, and `learning.py` handles lecture/guide page workflows. Database setup adds tables without replacing existing coursework.

## Tests and prototypes

```sh
python -m unittest discover -s tests -v
raco test racket/DSL_1.rkt racket/DSL_2.rkt
python -m prototypes.imperative
python -m prototypes.object_oriented
racket prototypes/functional.rkt
sqlite3 :memory: < prototypes/declarative.sql
```

The first three prototypes return 86 or 86.0. The SQL prototype returns A. If Racket is missing, one Python integration test reports a skip instead of claiming that Racket passed.

See `docs/IMPLEMENTATION.md` for the paradigm mapping and architecture, `docs/AUDIT.md` for the original code and correction, and `docs/TEST_RESULTS.txt` for this build's test output.

## Storage and scope

Data lives in `instance/studytrack.sqlite`. Back up that file while the app is stopped to preserve your coursework. The source ZIP excludes the database, environments and secrets. This first version binds to 127.0.0.1 and has no login or per-student isolation. Do not expose it as a multi-user service. A public version needs authentication and ownership checks before deployment.

Implemented now: course creation, assignment creation/deletion, score/completion updates, weighted progress, upcoming/overdue lists, rule-based plans, review/save, four prototypes, two integrated DSLs, an optional AI adapter and test evidence.

Also implemented: lecture uploads, target-grade calculations, source-based study guides and recall checks, optional AI explanations, and review/download.

Final submission preparation (November 8, 2026): the company assistants, report, company model paper and presentation have been prepared. The current evidence records 33 passing Python tests, 16 passing Racket checks and all four prototype outputs. Live AI testing and a human-reviewed audit score still remain. Full conversational tutoring, GPA policy, user accounts and richer course editing are future features, not final-build claims. The final report uses a provisional 87/100 self-assessment, not an instructor grade.

## Company AI assistants

Two task-specific assistants are now callable with the same server-side API configuration:

```sh
python -m studytrack.company_assistants company examples/company-brief.txt
python -m studytrack.company_assistants racket examples/dsl-brief.txt
```

Exact prompts live in `agents/`. These are single-request drafting assistants, not autonomous agents with tools. They return proposals for human review and never execute generated Racket code or modify project files. Their prompt routing and errors have mock tests; live outputs remain unverified without API credentials.

To capture a real API result using only fictional lecture content:

```sh
python tools/verify_live_ai.py --run --output live-ai-evidence.json
```

Review the saved answer against its source before treating the live AI requirement as complete. Do not submit credentials. A localhost link works only on the computer running the server; arrange source-based local execution or an instructor-approved demonstration for assessment.
