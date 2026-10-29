#!/usr/bin/env python3
"""Build the public web copy of the General CV.

The web copy differs from the source CV in exactly two ways:

1. the phone number is removed from the header;
2. the GPA line is removed from the education section.

Every edit must match exactly once, so a change in the CV's structure stops the
build instead of silently publishing something unintended. The research section
is published as written, but the build stops whenever it changes, so new
research wording is reviewed before it goes public.

When built to the default output, the PDF is written to assets/Eric-Wang-CV.pdf
and copied to assets/Yi-Fan-Eric-Wang-CV.pdf, the earlier name, so links to it
keep working.

Usage: python3 scripts/build_cv.py PATH/TO/CV.tex [-o OUTPUT.pdf]
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
DEFAULT_OUTPUT = ASSETS / "Eric-Wang-CV.pdf"
LEGACY_OUTPUT = ASSETS / "Yi-Fan-Eric-Wang-CV.pdf"

# Fingerprint of the source CV's research section (see research_fingerprint).
# When that section changes, the build stops so the new wording can be reviewed
# before it is published; then update this value.
EXPECTED_RESEARCH_SHA256 = "bd4e2826d384a1056c2d710c61460ed2bf779a1798c9743eeed0be7779d59c4a"

PDF_METADATA = (
    r"\hypersetup{pdftitle={Eric Wang — CV}, pdfauthor={Eric Wang},"
    r" pdfdisplaydoctitle=true, pdflang=en-US}"
)

PHONE_DEFINITION = re.compile(r"^\\newcommand\{\\ApplicantPhone\}\{([^}\n]*)\}[ \t]*\n", re.MULTILINE)
PHONE_IN_HEADER = re.compile(r"\\ApplicantPhone\{\}\s*\$\|\$[ \t]*")
GPA_ITEM = re.compile(r"^[ \t]*\\resumeItem\{\\textbf\{\\scshape GPA\}:\s*([^%{}\n]*)\}[ \t]*\n", re.MULTILINE)
GPA_VALUE = re.compile(r"\d+\.\d+")
RESEARCH_MARKER = re.compile(r"^%-+RESEARCH EXPERIENCE-+[ \t]*$", re.MULTILINE)
WORK_MARKER = re.compile(r"^%-+WORK EXPERIENCE-+[ \t]*$", re.MULTILINE)
BEGIN_DOCUMENT = re.compile(r"^\\begin\{document\}", re.MULTILINE)
PAGES_WRITTEN = re.compile(r"Output written on cv\.pdf \((\d+) pages?")


class BuildError(Exception):
    """The source CV no longer has the structure this build expects."""


def strip_comments(text: str) -> str:
    """Drop full-line LaTeX comments."""
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("%"))


def research_fingerprint(block: str) -> str:
    """SHA-256 of a research section, ignoring comments and whitespace layout."""
    normalized = " ".join(strip_comments(block).split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _replace_once(pattern: re.Pattern[str], text: str, replacement: str, what: str) -> str:
    new_text, count = pattern.subn(lambda _match: replacement, text)
    if count != 1:
        raise BuildError(f"expected exactly one {what}, found {count}")
    return new_text


def _research_span(text: str) -> tuple[int, int]:
    starts = list(RESEARCH_MARKER.finditer(text))
    ends = list(WORK_MARKER.finditer(text))
    if len(starts) != 1 or len(ends) != 1:
        raise BuildError(
            f"expected one research marker and one work marker, found {len(starts)} and {len(ends)}"
        )
    start, end = starts[0].end(), ends[0].start()
    if start >= end:
        raise BuildError("the research marker must come before the work marker")
    return start, end


def make_web_copy(src: str, expected_research_sha256: str = EXPECTED_RESEARCH_SHA256) -> str:
    """Return the web copy's LaTeX source."""
    definitions = PHONE_DEFINITION.findall(src)
    if len(definitions) != 1:
        raise BuildError(f"expected exactly one phone macro definition, found {len(definitions)}")
    phone_digits = re.sub(r"\D", "", definitions[0])

    gpa_items = GPA_ITEM.findall(src)
    if len(gpa_items) != 1:
        raise BuildError(f"expected exactly one GPA line, found {len(gpa_items)}")
    gpa_value = GPA_VALUE.search(gpa_items[0])
    if gpa_value is None:
        raise BuildError("the GPA line has no GPA value")

    text = _replace_once(PHONE_DEFINITION, src, "", "phone macro definition")
    text = _replace_once(PHONE_IN_HEADER, text, "", "phone entry in the header")
    text = _replace_once(GPA_ITEM, text, "", "GPA line")

    start, end = _research_span(text)
    actual = research_fingerprint(text[start:end])
    if actual != expected_research_sha256:
        raise BuildError(
            f"research section changed (fingerprint {actual}). Review the new research wording "
            "for public use, then set EXPECTED_RESEARCH_SHA256 in scripts/build_cv.py to this value."
        )

    text = _replace_once(BEGIN_DOCUMENT, text, PDF_METADATA + "\n\\begin{document}", "\\begin{document}")

    visible = strip_comments(text)
    if "\\ApplicantPhone" in visible:
        raise BuildError("the phone macro is still referenced")
    remaining_digits = re.sub(r"\D", "", visible)
    if any(tail and tail in remaining_digits for tail in (phone_digits[-7:], phone_digits[-10:])):
        raise BuildError("the phone number is still present")
    if "gpa" in visible.lower():
        raise BuildError("a GPA mention is still present")
    if gpa_value.group() in visible:
        raise BuildError("the GPA value is still present")
    return text


def _source_date_epoch(source: Path) -> str | None:
    """Commit time of the source file, so rebuilding unchanged input gives the same PDF."""
    result = subprocess.run(
        ["git", "-C", str(source.parent), "log", "-1", "--format=%ct", "--", source.name],
        capture_output=True,
        text=True,
        check=False,
    )
    epoch = result.stdout.strip()
    return epoch if result.returncode == 0 and epoch.isdigit() else None


def compile_pdf(tex: str, output: Path, source: Path) -> int:
    """Compile the LaTeX source to OUTPUT and return the page count."""
    env = dict(os.environ)
    epoch = _source_date_epoch(source)
    if epoch:
        env.update(SOURCE_DATE_EPOCH=epoch, FORCE_SOURCE_DATE="1")

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        (workdir / "cv.tex").write_text(tex, encoding="utf-8")
        result = subprocess.run(
            ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", "cv.tex"],
            cwd=workdir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        log_path = workdir / "cv.log"
        log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
        if result.returncode != 0:
            tail = "\n".join((log or result.stdout + result.stderr).splitlines()[-30:])
            raise BuildError(f"LaTeX failed:\n{tail}")

        written = PAGES_WRITTEN.findall(log)
        if not written:
            raise BuildError("could not find the page count in the LaTeX log")
        pages = int(written[-1])

        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(workdir / "cv.pdf", output)
    return pages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the public web copy of the General CV.")
    parser.add_argument("source", type=Path, help="path to the General CV .tex file")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT, help="PDF to write")
    args = parser.parse_args(argv)

    try:
        tex = make_web_copy(args.source.read_text(encoding="utf-8"))
        pages = compile_pdf(tex, args.output, args.source.resolve())
        if args.output.resolve() == DEFAULT_OUTPUT:
            shutil.copyfile(args.output, LEGACY_OUTPUT)
    except (BuildError, OSError) as error:
        print(f"build_cv: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {args.output} ({pages} pages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
