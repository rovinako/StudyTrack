"""Extract lecture text with source locations. Never execute uploaded content."""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile
from defusedxml import ElementTree as XML
from pypdf import PdfReader

MAX_BYTES = 10 * 1024 * 1024
MAX_TEXT = 120_000
MAX_PARTS = 150
EXTENSIONS = {".pdf", ".pptx", ".docx", ".txt", ".md"}


def clean(text):
    text = text.replace("\x00", "")
    return "\n".join(" ".join(line.split()) for line in text.splitlines()).strip()


def extract(path):
    """Runs inside a short-lived worker, with a parent-enforced timeout."""
    suffix = Path(path).suffix.lower()
    sections = []
    if suffix in {".txt", ".md"}:
        try:
            value = Path(path).read_text(encoding="utf-8-sig")
        except UnicodeError:
            raise ValueError("Save text files as UTF-8, then upload again.") from None
        sections = [
            {"location": f"Section {i}", "text": part}
            for i, part in enumerate(re.split(r"\n\s*\n", value), 1)
            if part.strip()
        ]
    elif suffix == ".pdf":
        reader = PdfReader(path)
        if reader.is_encrypted:
            raise ValueError("Upload an unencrypted PDF.")
        if len(reader.pages) > MAX_PARTS:
            raise ValueError("Split this PDF into files of 150 pages or fewer.")
        for i, page in enumerate(reader.pages, 1):
            sections.append(
                {"location": f"Page {i}", "text": page.extract_text() or ""}
            )
    elif suffix in {".pptx", ".docx"}:
        with ZipFile(path) as archive:
            if (
                len(archive.infolist()) > 5000
                or sum(x.file_size for x in archive.infolist()) > 50 * 1024 * 1024
            ):
                raise ValueError(
                    "This document is too large after decompression. Split it first."
                )
            if suffix == ".pptx":
                # Presentation order can differ from slide filenames after slides are moved.
                ns = {
                    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
                    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
                }
                pres = XML.fromstring(archive.read("ppt/presentation.xml"))
                rels = XML.fromstring(archive.read("ppt/_rels/presentation.xml.rels"))
                targets = {
                    r.attrib["Id"]: r.attrib["Target"]
                    for r in rels
                    if r.attrib.get("TargetMode") != "External"
                }
                slides = pres.findall("p:sldIdLst/p:sldId", ns)
                if len(slides) > MAX_PARTS:
                    raise ValueError(
                        "Split this presentation into files of 150 slides or fewer."
                    )
                for i, slide in enumerate(slides, 1):
                    target = targets[slide.attrib[f"{{{ns['r']}}}id"]]
                    name = (
                        target.lstrip("/")
                        if target.startswith("/")
                        else "ppt/" + target
                    )
                    node = XML.fromstring(archive.read(name))
                    paragraphs = node.findall(
                        ".//{http://schemas.openxmlformats.org/drawingml/2006/main}p"
                    )
                    text = "\n".join("".join(p.itertext()) for p in paragraphs)
                    sections.append({"location": f"Slide {i}", "text": text})
            else:
                node = XML.fromstring(archive.read("word/document.xml"))
                paragraphs = node.findall(
                    ".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
                )
                for i, paragraph in enumerate(paragraphs, 1):
                    text = "".join(paragraph.itertext())
                    sections.append({"location": f"Paragraph {i}", "text": text})
    else:
        raise ValueError("Use a PDF, PPTX, DOCX, TXT, or Markdown file.")
    total = sum(len(s["text"]) for s in sections)
    if total > MAX_TEXT:
        raise ValueError(
            "This lecture contains too much text. Split it into smaller files (120,000 characters each)."
        )
    result = []
    for section in sections:
        text = clean(section["text"])
        # Bounded chunks make source references and retrieval manageable.
        lines = re.findall(r".{1,1100}(?:\s|$)|.{1,1100}", text, re.S)
        for i, value in enumerate(lines, 1):
            if value.strip():
                location = section["location"] + (
                    f", part {i}" if len(lines) > 1 else ""
                )
                result.append({"location": location, "text": value.strip()})
    if sum(len(s["text"]) for s in result) < 40:
        raise ValueError(
            "No usable lecture text found. Scanned pages and slide images need OCR first, or upload text notes."
        )
    if len(result) > 600:
        raise ValueError(
            "This lecture has too many sections. Split it into smaller files."
        )
    return result


def read_upload(upload):
    filename = (upload.filename or "").replace("\\", "/").rsplit("/", 1)[-1][:180]
    suffix = Path(filename).suffix.lower()
    if suffix not in EXTENSIONS:
        raise ValueError("Use a PDF, PPTX, DOCX, TXT, or Markdown file.")
    data = upload.read(MAX_BYTES + 1)
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Choose a nonempty lecture file smaller than 10 MB.")
    # Original files are temporary and removed even when parsing fails.
    with tempfile.TemporaryDirectory(prefix="studytrack-lecture-") as folder:
        path = Path(folder) / ("lecture" + suffix)
        path.write_bytes(data)
        try:
            process = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), str(path)],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            payload = json.loads(process.stdout)
        except (subprocess.TimeoutExpired, OSError, ValueError):
            raise ValueError(
                "This file could not be read in time. Try a smaller file or export text notes."
            ) from None
        if process.returncode or "error" in payload:
            raise ValueError(payload.get("error", "This lecture could not be read."))
    return filename, payload["sections"]


if __name__ == "__main__":
    try:
        # Keep a malformed compressed document from exhausting the local app process.
        if sys.platform != "win32":
            import resource

            limits = [(resource.RLIMIT_CPU, 15)]
            # macOS does not reliably support lowering Python data limits.
            if sys.platform.startswith("linux"):
                limits.append((resource.RLIMIT_AS, 512 * 1024 * 1024))
            for kind, budget in limits:
                _, hard = resource.getrlimit(kind)
                limit = budget if hard == resource.RLIM_INFINITY else min(budget, hard)
                resource.setrlimit(kind, (limit, hard))
        print(json.dumps({"sections": extract(sys.argv[1])}))
    except ValueError as error:
        print(json.dumps({"error": str(error)}))
        sys.exit(1)
    except Exception:
        print(
            json.dumps(
                {
                    "error": "The file is damaged, unsupported, or too complex. Export it as a text PDF or TXT and try again."
                }
            )
        )
        sys.exit(1)
