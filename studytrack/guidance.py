"""Pure goal mathematics and lecture selection, separate from pages and storage."""

import re
from collections import Counter
from .domain import number
from .racket_bridge import calculate

STOP = set(
    "the a an and or of to in for with on at is are was were this that it as be by from your you how what which lecture slide course".split()
)


def target_progress(summary, target):
    target = number(target, "Target grade", 0, 100)
    remaining = max(0, 100 - summary["graded_weight"])
    missing = max(0, 100 - summary["configured_weight"])
    earned = summary["earned"]
    required = max(0, (target - earned) * 100 / remaining) if remaining > 1e-6 else None
    maximum = min(100, earned + remaining)
    if remaining <= 1e-6:
        status = "complete"
        message = f"All course weight is graded. Final result: {earned:.1f}%."
    elif target <= earned + 1e-6:
        status = "secured"
        message = "Your recorded points already meet this target, even if the remaining scores are zero."
    elif required > 100 + 1e-6:
        status = "unreachable"
        message = f"This target is above the maximum possible {maximum:.1f}% under these weights. Review the target or discuss options with your instructor."
    else:
        status = "possible"
        message = f"You need a weighted average of {required:.1f}% across the remaining {remaining:g}% of course weight."
    return {
        "target": target,
        "required": required,
        "remaining": remaining,
        "missing": missing,
        "maximum": maximum,
        "status": status,
        "message": message,
    }


def words(value):
    return [
        w for w in re.findall(r"[\w'-]+", value.lower()) if len(w) > 2 and w not in STOP
    ]


def choose_sources(lectures, focus, count=6):
    query = set(words(focus))
    candidates = []
    for lecture in lectures:
        for i, section in enumerate(lecture["sections"]):
            if len(section["text"].strip()) < 40:
                continue
            counts = Counter(words(section["text"]))
            score = sum(min(counts[w], 4) for w in query)
            candidates.append(
                {
                    "id": f"L{lecture['id']}-{i+1}",
                    "lecture_id": lecture["id"],
                    "section": i + 1,
                    "lecture": lecture["title"],
                    **section,
                    "score": score,
                }
            )
    if query:
        candidates = sorted(
            (s for s in candidates if s["score"]), key=lambda s: -s["score"]
        )
        if not candidates:
            raise ValueError(
                "That topic was not found in the selected lectures. Try a word from your notes or leave the focus empty for an overview."
            )
    else:
        # Round-robin across lectures avoids filling the guide with only the first file.
        candidates.sort(key=lambda s: (s["section"], s["lecture_id"]))
    result, seen = [], set()
    for source in candidates:
        key = " ".join(source["text"].lower().split())
        if key not in seen:
            result.append(source)
            seen.add(key)
        if len(result) == count:
            break
    if not result:
        raise ValueError(
            "The selected files do not have enough readable text. Upload text-based lecture notes."
        )
    return result


def topic_name(source):
    first = source["text"].splitlines()[0].strip()
    if 5 <= len(first) <= 85:
        return first.rstrip(".:;")
    terms = [w for w, _ in Counter(words(source["text"])).most_common(3)]
    return " / ".join(terms).capitalize() or source["location"]


def recall_question(source):
    sentences = re.split(r"(?<=[.!?])\s+|\n+", source["text"])
    candidates = [s.strip() for s in sentences if 45 <= len(s.strip()) <= 300]
    heading_terms = set(words(topic_name(source)))
    sentence = max(
        candidates,
        key=lambda s: len(set(words(s)) & heading_terms),
        default=source["text"][:300],
    )
    terms = [
        w for w in re.findall(r"\b[^\W\d_]{5,}\b", sentence) if w.lower() not in STOP
    ]
    if not terms:
        return {
            "question": "Explain this passage in your own words, then check it against the source.",
            "answer": sentence,
        }
    term = max(terms, key=len)
    return {
        "question": sentence.replace(term, "________", 1),
        "answer": term,
        "evidence": sentence,
    }


def make_guide(course, summary, lectures, available, focus="", assessment=None):
    minutes = number(available, "Study time", 10, 480)
    if not minutes.is_integer():
        raise ValueError("Study time must be a whole number.")
    available = int(minutes)
    goal = target_progress(summary, course["target"])
    count = min(6, max(1, available // 15))
    sources = choose_sources(lectures, focus, count)
    # Higher required averages dedicate more of the same budget to active practice.
    demanding = goal["required"] is not None and goal["required"] >= 90
    practice_share = 0.5 if demanding else 0.35
    target_label = "Practice emphasis" if demanding else "Understand and recall"
    base, extra = divmod(available, len(sources))
    tasks = [{"id": i + 1, "minutes": base + (i < extra)} for i in range(len(sources))]
    allocation, engine = calculate("plan", {"tasks": tasks, "available": available})
    sessions = []
    for item in allocation["sessions"]:
        source = sources[item["id"] - 1]
        total = item["minutes"]
        practice = max(1, round(total * practice_share))
        check = max(1, round(total * 0.2))
        read = total - practice - check
        sessions.append(
            {
                "topic": topic_name(source),
                "source": source,
                "minutes": total,
                "read": read,
                "practice": practice,
                "check": check,
                "question": recall_question(source),
            }
        )
    return {
        "course": course["title"],
        "goal": goal,
        "current": summary["current"],
        "available": available,
        "focus": focus,
        "assessment": assessment,
        "approach": target_label,
        "engine": engine,
        "sessions": sessions,
        "mode": "Lecture-based guide",
        "ai_sections": [],
    }


def guide_text(guide):
    g = guide["goal"]
    lines = [
        f"{guide['course']} — Study guide",
        f"Target: {g['target']:g}%",
        g["message"],
    ]
    if g["missing"] > 1e-6:
        lines.append(
            f"Assumption: {g['missing']:g}% of course weight is not entered yet. The calculation assumes the course totals 100%."
        )
    lines += [
        f"Study budget: {guide['available']} minutes. {guide['approach']}.",
        "This is a study strategy, not a grade prediction or guarantee.",
    ]
    if guide["assessment"]:
        a = guide["assessment"]
        lines.append(
            f"Preparing for {a['title']} — due {a['due']}, weight {a['weight']:g}%."
        )
    for session in guide["sessions"]:
        source = session["source"]
        lines += [
            "",
            f"{session['topic']} — {session['minutes']} minutes",
            f"Source [{source['id']}]: {source['lecture']}, {source['location']}",
            f"Read and outline: {session['read']} min. Close notes and explain/work an example: {session['practice']} min. Check and correct: {session['check']} min.",
            "Key passage: " + source["text"],
            "Recall check: " + session["question"]["question"],
            "Answer: " + session["question"]["answer"],
        ]
    for section in guide["ai_sections"]:
        lines += [
            "",
            f"AI explanation [{section['source_id']}]: {section['explanation']}",
            f"Practice: {section['question']}",
            f"Suggested answer: {section['answer']}",
        ]
    return "\n".join(lines)
