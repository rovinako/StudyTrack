"""Opt-in live check using fictional lecture text, never the student's database."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studytrack import ai
from studytrack.guidance import make_guide
from studytrack.functional import grade_summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true', help='Send a small fictional example to the configured API (usage charges may apply).')
    parser.add_argument('--output', type=Path, default=Path('live-ai-evidence.json'))
    args = parser.parse_args()
    if not args.run:
        parser.exit(1, 'Use --run to send the fictional example to the API.\n')
    if args.output.exists():
        parser.exit(1, 'Choose a new evidence filename to preserve previous results.\n')
    lecture = {'id':1,'title':'Fictional recursion example','sections':[{'location':'Section 1','text':'Recursion\nA recursive function solves a problem using smaller inputs. A base case stops recursion. Every recursive step must move closer to the base case.'}]}
    guide = make_guide({'title':'Demo','target':90}, grade_summary([]), [lecture], 30, 'recursion')
    try:
        sections = ai.lecture_coach(guide)
    except ValueError as error:
        parser.exit(1, f'{error}\n')
    record = {'checked_utc':datetime.now(timezone.utc).isoformat(), 'automated_result':'completed with valid source IDs and matching quotations', 'human_review':'PENDING: check correctness and usefulness against the supplied passage', 'sources':[lecture], 'response':sections}
    args.output.write_text(json.dumps(record, indent=2), encoding='utf-8')
    print(f'Live response saved to {args.output}. Human review is still required.')

if __name__ == '__main__': main()
