#!/usr/bin/env python3
"""Build the public web copy of the General CV.

The web copy differs from the source CV in exactly three ways:

1. the phone number is removed from the header;
2. the GPA clause is removed from the education section;
3. the research section is replaced by the wording used on the website.

Every edit must match exactly once, so a change in the CV's structure stops the
build instead of silently publishing something unintended.

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

DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "assets" / "Yi-Fan-Eric-Wang-CV.pdf"

# Fingerprint of the source CV's research section (see research_fingerprint).
# When that section changes, the build stops so RESEARCH_BLOCK can be reviewed
# before anything is published; then update this value.
EXPECTED_RESEARCH_SHA256 = "97484892008f71cee772e5553188ff0a2512f2f37f6facfc84db3996f980c20f"

RESEARCH_BLOCK = r"""\section{Research Experience}
  \resumeSubHeadingListStart
    \resumeProjectHeading{\textbf{Undergraduate Research Student, University of Toronto}}{Toronto, ON, Canada, Sep. 2026 -- Present}
    \resumeItemListStart
      \resumeItem{Member of a three-student undergraduate team on ``Correlation-Augmented Neural Retrieval - From Hard Filtering to Spectral Diffusion,'' supervised by Professor Nick Koudas (Department of Computer Science)}
      \resumeItem{Project tests whether adding a sparse graph of corpus term-association estimates to a dense neural retriever can reduce off-topic results, recover relevant passages that share no query terms, and control query cost}
      \resumeItem{Team plans to compare four ways to inject that signal: candidate pre-filtering, metric warping for re-scoring, multi-hop graph diffusion, and contrastive fine-tuning, with an evaluation protocol and an assumption audit}
    \resumeItemListEnd
  \resumeSubHeadingListEnd

"""

PDF_METADATA = (
    r"\hypersetup{pdftitle={Yi Fan (Eric) Wang — CV}, pdfauthor={Yi Fan (Eric) Wang},"
    r" pdfdisplaydoctitle=true, pdflang=en-US}"
)

PHONE_DEFINITION = re.compile(r"^\\newcommand\{\\ApplicantPhone\}\{([^}\n]*)\}[ \t]*\n", re.MULTILINE)
PHONE_IN_HEADER = re.compile(r"\\ApplicantPhone\{\}\s*\$\|\$[ \t]*")
GPA_CLAUSE = re.compile(r"\d\.\d\d annual GPA \([^)]*\);\s*")
RESEARCH_MARKER = re.compile(r"^%-+RESEARCH EXPERIENCE-+[ \t]*$", re.MULTILINE)
WORK_MARKER = re.compile(r"^%-+WORK EXPERIENCE-+[ \t]*$", re.MULTILINE)
BEGIN_DOCUMENT = re.compile(r"^\\begin\{document\}", re.MULTILINE)
NEWPAGE = re.compile(r"\\newpage\b")
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

    text = _replace_once(PHONE_DEFINITION, src, "", "phone macro definition")
    text = _replace_once(PHONE_IN_HEADER, text, "", "phone entry in the header")
    text = _replace_once(GPA_CLAUSE, text, "", "GPA clause")

    start, end = _research_span(text)
    actual = research_fingerprint(text[start:end])
    if actual != expected_research_sha256:
        raise BuildError(
            f"research section changed (fingerprint {actual}). Review RESEARCH_BLOCK in "
            "scripts/build_cv.py against the new CV, then set EXPECTED_RESEARCH_SHA256 to this value."
        )
    text = text[:start] + "\n" + RESEARCH_BLOCK + text[end:]

    text = _replace_once(BEGIN_DOCUMENT, text, PDF_METADATA + "\n\\begin{document}", "\\begin{document}")

    visible = strip_comments(text)
    if "\\ApplicantPhone" in visible:
        raise BuildError("the phone macro is still referenced")
    remaining_digits = re.sub(r"\D", "", visible)
    if any(tail and tail in remaining_digits for tail in (phone_digits[-7:], phone_digits[-10:])):
        raise BuildError("the phone number is still present")
    if "gpa" in visible.lower():
        raise BuildError("a GPA mention is still present")
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
        expected_pages = len(NEWPAGE.findall(strip_comments(tex))) + 1
        if pages != expected_pages:
            raise BuildError(
                f"the PDF has {pages} pages but the source has {expected_pages - 1} page break(s); "
                "a page probably overflowed"
            )

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
    except (BuildError, OSError) as error:
        print(f"build_cv: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {args.output} ({pages} pages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
