"""Tests for build_cv's source transform. Fixtures are synthetic; none of them is real CV content.

Run with: python3 -m unittest discover -s scripts
"""

import re
import unittest

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
Academic Performance: 9.99 annual GPA (Fall 2099 -- Winter 2100); A+ in Example Studies
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

    def test_removes_gpa_clause_and_keeps_grade_highlights(self) -> None:
        out = web_copy()
        self.assertNotIn("GPA", out)
        self.assertIn("Academic Performance: A+ in Example Studies", out)

    def test_replaces_research_section_when_fingerprint_matches(self) -> None:
        out = web_copy()
        self.assertNotIn("widgets", out)
        self.assertIn(build_cv.RESEARCH_BLOCK, out)
        self.assertLess(out.index("RESEARCH EXPERIENCE"), out.index(build_cv.RESEARCH_BLOCK))
        self.assertLess(out.index(build_cv.RESEARCH_BLOCK), out.index("WORK EXPERIENCE"))

    def test_adds_pdf_metadata_before_document(self) -> None:
        out = web_copy()
        self.assertIn(build_cv.PDF_METADATA + "\n\\begin{document}", out)

    def test_comment_only_edit_still_matches(self) -> None:
        edited = FIXTURE.replace("% Sources: example comment", "% Sources: re-sourced comment")
        self.assertNotIn("widgets", web_copy(edited))

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

    def test_missing_gpa_clause_fails(self) -> None:
        edited = FIXTURE.replace("9.99 annual GPA (Fall 2099 -- Winter 2100); ", "")
        with self.assertRaisesRegex(build_cv.BuildError, "GPA clause"):
            web_copy(edited)


if __name__ == "__main__":
    unittest.main()
