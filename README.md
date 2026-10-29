# EricWcr7.github.io

Personal website of Eric Wang, published with GitHub Pages at https://ericwcr7.github.io/.

The site is a single static page with no build step and no JavaScript: `index.html`, `assets/site.css`, and a few assets. `.nojekyll` tells GitHub Pages to serve the files as they are.

## Preview locally

```bash
python3 -m http.server 8765
```

Then open http://localhost:8765/.

## Content

Every claim on the page comes from my verified career records and follows the wording and style of my current CV and résumés, except that the page keeps languages, interests, and team details. Like the CV, the page lists relevant courses by plain name, with no grades. Update the page by hand when a record changes.

## Updating the timeline chart

The chart measures time in months since September 2022: a month's position is `(year - 2022) * 12 + (month - 9)`, so May 2025 is 32. In `index.html`, bars set `--start` and `--end` (the month after the last month), dots set `--at` (the middle of the month, such as 27.5 for December 2024), and bars for ongoing work use the `is-ongoing` class.

`--asof` in `assets/site.css` is the date the page was last checked (49.9 is October 29, 2026). When it changes, update the "Oct 2026" label, the chart caption, and the footer's "Updated" date in `index.html` to match. `--span` (58) ends the axis after June 2027.

## Rebuilding the CV

`assets/Eric-Wang-CV.pdf` is a web copy of my General CV, built by `scripts/build_cv.py`. The script leaves out the phone number and GPA; its docstring lists every change. It also copies the PDF to `assets/Yi-Fan-Eric-Wang-CV.pdf`, the earlier name, so old links keep working. To rebuild it after the CV changes:

```bash
python3 -m unittest discover -s scripts
```

```bash
python3 scripts/build_cv.py path/to/CV.tex
```

The build needs `latexmk` and stops if the CV's structure has moved. If it reports that the research section changed, check that the new research wording is fine to publish, then set `EXPECTED_RESEARCH_SHA256` in `scripts/build_cv.py` to the fingerprint the build printed.

## Regenerating the share image

`assets/og-image.png` is a 1200 × 630 screenshot of `scripts/og-card.html`, taken at device scale 1 in the light theme while the local preview is running.
