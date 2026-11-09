"""Two task-specific AI assistants. Draft output never executes or changes the app."""
import argparse
from pathlib import Path
from .ai import _generate

PROMPTS = Path(__file__).resolve().parents[1] / "agents"


def draft(assistant, request):
    if assistant not in {"company", "racket"}:
        raise ValueError("Choose company or racket.")
    if not isinstance(request, str) or not 1 <= len(request.strip()) <= 12000:
        raise ValueError("Provide 1–12,000 characters of requirements.")
    instructions = (PROMPTS / f"{assistant}.txt").read_text()
    return _generate({"requirements": request.strip()}, instructions, 5000)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assistant", choices=["company", "racket"])
    parser.add_argument("request_file", type=Path)
    args = parser.parse_args()
    try:
        if args.request_file.stat().st_size > 48000:
            raise ValueError("The request file is too large.")
        print(draft(args.assistant, args.request_file.read_text(encoding="utf-8")))
    except (ValueError, OSError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
