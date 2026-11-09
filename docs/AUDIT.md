# Initial paradigm audit: agent review, pending student sign-off

## Process record

Date: October 5, 2026. Target: the pure Python fallback in `studytrack/functional.py`, a real module used by the application when Racket is unavailable.

Exact user request that initiated implementation:

> But here is the plan, that i have for this project so i want to start implementing it now, and then do the powerpoint presentation.

Exact clarification answer:

> Yes, start with that StudyTrack plan

The preceding conversation and the supplied first PowerPoint established Flask, SQLite, Racket, grades, deadlines and an AI assistant. Codex generated the original implementation as part of this conversation. There was no separate external model prompt for this module. The model identifier was not recorded. Do not invent one or describe this as a separate generation experiment.

The untouched original generated file is `audit/functional_original.py`. The corrected file is `../studytrack/functional.py`. The transcript holds the original generation and subsequent correction. This is an agent self-review with automated checks, not independent human approval.

## Findings and corrections

1. **Technical correctness:** the original grade function assumed validated scores and weights. A direct call with score 110 returned 110 instead of rejecting it. The Racket DSL rejected the same invalid input. The corrected function checks finite numbers, ranges and aggregate weight before calculating.
2. **Technical correctness and cross-paradigm consistency:** the original allocator accepted a negative time budget and duplicate task IDs. The corrected function checks integer bounds and unique positive IDs. Its boundary behavior now agrees with the Racket interpreter.
3. **Paradigm fidelity:** the original transformation used `filter`, `map`, `reduce` and newly constructed values. It did not mutate input or perform I/O. No mutation violation was found. The correction retains that property. Local bindings are not mutations of input data.

The existing HTTP form validations limited exposure to ordinary invalid user input, but direct module calls still needed their own contract. Validation belongs at both the input boundary and the reusable calculation boundary.

## Reproduction and tests

`audit/reproduce.py` loads the original and corrected versions and prints the actual before/after behavior. `AUDIT_RESULTS.txt` records the run. Automated tests additionally cover unchanged inputs, repeatable outputs, empty inputs, zero versus missing grades, duplicate IDs, time budgets and real Racket/Python parity.

The imperative prototype explicitly updates local accumulators. That mutation is intentional and appropriate for its paradigm. The functional calculation constructs new values instead. Both compute 86% for the complete-course fixture. The SQL component declaratively selects records; it is not a substitute for the grading calculation.

## Rubric status

Paradigm fidelity (30), technical correctness (25), written analysis (25), AI-process documentation (10), and cross-paradigm comparison (10) form a 100-point rubric. No final score is assigned. The student should inspect the original code, reproduce the correction, explain the differences and sign off before using this as the completed course audit. The professor may require a separate, focused prompt/code-generation record; the broad conversation record above is transparent about what actually happened.

## November 8 final submission update

The Canvas weights were verified: fidelity 30, correctness 25, analysis 25, AI-process documentation 10, comparison 10. The final report provides a provisional AI-assisted self-assessment of 87/100 (28 + 23 + 22 + 5 + 9), not an instructor grade or human sign-off. Missing focused generation metadata limits process documentation. Rovena Nako must inspect and approve or revise the assessment. Current reproduction and test outputs are in evidence/.
