"""Tests for build_cv's source transform. Fixtures are synthetic; none of them is real CV content.

Run with: python3 -m unittest discover -s scripts
"""

import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import build_cv

RESEARCH_BODY = r"""
\section{Research Experience}
  % Sources: example comment
  \resumeItem{An example research bullet about widgets}
"""

FIXTURE = (
    r"""\documentclass{article}
\newcommand{\ApplicantLocation}{Springfield}
\newcommand{\ApplicantPhone}{+1 (555) 010-0199}
\newcommand{\ApplicantEmail}{someone@example.com}
\begin{document}
%----------HEADING----------
\begin{center}
    \small \ApplicantLocation{} $|$ \ApplicantPhone{} $|$
    \href{mailto:someone@example.com}{\ApplicantEmail}
\end{center}
%-----------EDUCATION-----------
\section{Education}
  % Results: the GPA line below comes from an example record.
  \resumeItem{\textbf{Example Degree}: Example Studies}
  \resumeItem{\textbf{\scshape GPA}: 9.99 (Fall 2099 -- Winter 2100)}
  \resumeItem{\textbf{\scshape Relevant Courses}: Example Studies}
%-----------RESEARCH EXPERIENCE-----------"""
    + RESEARCH_BODY
    + r"""%-----------WORK EXPERIENCE-----------
\section{Work Experience}
Worked somewhere.
\newpage
More.
\end{document}
"""
)

FIXTURE_HASH = build_cv.research_fingerprint(RESEARCH_BODY)


def web_copy(src: str = FIXTURE) -> str:
    return build_cv.make_web_copy(src, expected_research_sha256=FIXTURE_HASH)


class MakeWebCopyTests(unittest.TestCase):
    def test_removes_phone_and_keeps_single_separators(self) -> None:
        out = web_copy()
        self.assertNotIn("ApplicantPhone", out)
        self.assertNotIn("0100199", re.sub(r"\D", "", out))
        self.assertEqual(out.count("$|$"), 1)
        self.assertRegex(out, r"\\small \\ApplicantLocation\{\} \$\|\$\s*\n\s*\\href\{mailto:")

    def test_removes_gpa_line_and_keeps_neighbouring_lines(self) -> None:
        out = web_copy()
        self.assertNotIn("GPA", build_cv.strip_comments(out))
        self.assertNotIn("9.99", out)
        self.assertRegex(
            out,
            r"\\resumeItem\{\\textbf\{Example Degree\}: Example Studies\}\n"
            r"\s*\\resumeItem\{\\textbf\{\\scshape Relevant Courses\}: Example Studies\}",
        )

    def test_keeps_research_section_when_fingerprint_matches(self) -> None:
        out = web_copy()
        self.assertIn(RESEARCH_BODY, out)

    def test_adds_pdf_metadata_before_document(self) -> None:
        out = web_copy()
        self.assertIn(build_cv.PDF_METADATA + "\n\\begin{document}", out)

    def test_comment_only_edit_still_matches(self) -> None:
        edited = FIXTURE.replace("% Sources: example comment", "% Sources: re-sourced comment")
        self.assertIn("about widgets", web_copy(edited))

    def test_bullet_edit_fails(self) -> None:
        edited = FIXTURE.replace("about widgets", "about gadgets")
        with self.assertRaisesRegex(build_cv.BuildError, "research section changed"):
            web_copy(edited)

    def test_missing_marker_fails(self) -> None:
        edited = FIXTURE.replace("%-----------WORK EXPERIENCE-----------\n", "")
        with self.assertRaisesRegex(build_cv.BuildError, "work marker"):
            web_copy(edited)

    def test_markers_out_of_order_fails(self) -> None:
        swapped = (
            FIXTURE.replace("%-----------RESEARCH EXPERIENCE-----------", "@@R@@")
            .replace("%-----------WORK EXPERIENCE-----------", "%-----------RESEARCH EXPERIENCE-----------")
            .replace("@@R@@", "%-----------WORK EXPERIENCE-----------")
        )
        with self.assertRaisesRegex(build_cv.BuildError, "must come before"):
            web_copy(swapped)

    def test_duplicate_phone_macro_fails(self) -> None:
        doubled = FIXTURE.replace(
            r"\newcommand{\ApplicantEmail}",
            "\\newcommand{\\ApplicantPhone}{+1 (555) 010-0123}\n\\newcommand{\\ApplicantEmail}",
        )
        with self.assertRaisesRegex(build_cv.BuildError, "phone macro definition"):
            web_copy(doubled)

    def test_lingering_phone_macro_reference_fails(self) -> None:
        edited = FIXTURE.replace("Worked somewhere.", r"Worked somewhere. Call \ApplicantPhone{} anytime.")
        with self.assertRaisesRegex(build_cv.BuildError, "still referenced"):
            web_copy(edited)

    def test_phone_number_written_out_fails(self) -> None:
        edited = FIXTURE.replace("Worked somewhere.", "Worked somewhere. Phone 555-010-0199.")
        with self.assertRaisesRegex(build_cv.BuildError, "still present"):
            web_copy(edited)

    def test_missing_gpa_line_fails(self) -> None:
        edited = FIXTURE.replace("  \\resumeItem{\\textbf{\\scshape GPA}: 9.99 (Fall 2099 -- Winter 2100)}\n", "")
        with self.assertRaisesRegex(build_cv.BuildError, "GPA line"):
            web_copy(edited)

    def test_gpa_mentioned_elsewhere_fails(self) -> None:
        edited = FIXTURE.replace("Worked somewhere.", "Worked somewhere with a 9.99 GPA.")
        with self.assertRaisesRegex(build_cv.BuildError, "GPA mention"):
            web_copy(edited)

    def test_gpa_value_left_elsewhere_fails(self) -> None:
        edited = FIXTURE.replace("Worked somewhere.", "Worked somewhere, averaging 9.99.")
        with self.assertRaisesRegex(build_cv.BuildError, "GPA value"):
            web_copy(edited)

    def test_two_gpa_lines_fail(self) -> None:
        line = "  \\resumeItem{\\textbf{\\scshape GPA}: 9.99 (Fall 2099 -- Winter 2100)}\n"
        with self.assertRaisesRegex(build_cv.BuildError, "found 2"):
            web_copy(FIXTURE.replace(line, line + line))

    def test_relabelled_gpa_with_gpa_comment_elsewhere_fails(self) -> None:
        edited = FIXTURE.replace("\\scshape GPA}", "\\scshape Grade Point Average}").replace(
            "\\scshape Relevant Courses}: Example Studies}",
            "\\scshape Relevant Courses}: Example Studies} % GPA source: example",
        )
        with self.assertRaisesRegex(build_cv.BuildError, "GPA line"):
            web_copy(edited)

    def test_gpa_line_split_across_lines_fails(self) -> None:
        edited = FIXTURE.replace("9.99 (Fall 2099 -- Winter 2100)}", "9.99\n    (Fall 2099 -- Winter 2100)}")
        with self.assertRaisesRegex(build_cv.BuildError, "GPA line"):
            web_copy(edited)


class MainTests(unittest.TestCase):
    def run_main(self, tmp: Path, *extra: str) -> tuple[Path, Path]:
        source = tmp / "cv.tex"
        source.write_text("source", encoding="utf-8")
        default, legacy = tmp / "new.pdf", tmp / "old.pdf"

        def fake_compile(tex: str, output: Path, src: Path) -> int:
            output.write_text("pdf", encoding="utf-8")
            return 2

        with mock.patch.object(build_cv, "DEFAULT_OUTPUT", default), mock.patch.object(
            build_cv, "LEGACY_OUTPUT", legacy
        ), mock.patch.object(build_cv, "make_web_copy", return_value="tex"), mock.patch.object(
            build_cv, "compile_pdf", side_effect=fake_compile
        ), mock.patch("builtins.print"):
            self.assertEqual(build_cv.main([str(source), *extra]), 0)
        return default, legacy

    def test_default_output_is_copied_to_legacy_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            default, legacy = self.run_main(Path(tmp).resolve())
            self.assertEqual(legacy.read_text(encoding="utf-8"), "pdf")

    def test_other_output_is_not_copied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            other = Path(tmp).resolve() / "other.pdf"
            default, legacy = self.run_main(Path(tmp).resolve(), "-o", str(other))
            self.assertTrue(other.exists())
            self.assertFalse(legacy.exists())


if __name__ == "__main__":
    unittest.main()
