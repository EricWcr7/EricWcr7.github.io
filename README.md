# EricWcr7.github.io

Personal website of Yi Fan (Eric) Wang, published with GitHub Pages at https://ericwcr7.github.io/.

The site is a single static page with no build step and no JavaScript: `index.html`, `assets/site.css`, and a few assets. `.nojekyll` tells GitHub Pages to serve the files as they are.

## Preview locally

```bash
python3 -m http.server 8765
```

Then open http://localhost:8765/.

## Content

Every claim on the page comes from my verified career records and stays within the wording approved there. Course titles follow the University of Toronto Arts & Science calendar. Update the page by hand when a record changes.

## Updating the timeline chart

The chart measures time in months since September 2022: a month's position is `(year - 2022) * 12 + (month - 9)`, so May 2025 is 32. In `index.html`, bars set `--start` and `--end` (the month after the last month), dots set `--at` (the middle of the month, such as 27.5 for December 2024), and bars for ongoing work use the `is-ongoing` class.

`--asof` in `assets/site.css` is the date the page was last checked (49.1 is October 3, 2026). When it changes, update the "Oct 2026" label, the chart caption, and the footer's "Updated" date in `index.html` to match. `--span` (58) ends the axis after June 2027.

## Rebuilding the CV

`assets/Yi-Fan-Eric-Wang-CV.pdf` is a web copy of my General CV, built by `scripts/build_cv.py`. The script leaves out a few personal details and uses this page's public wording for the research section; its docstring lists every change. To rebuild it after the CV changes:

```bash
python3 -m unittest discover -s scripts
```

```bash
python3 scripts/build_cv.py path/to/CV.tex
```

The build needs `latexmk` and stops if the CV's structure has moved. If it reports that the research section changed, compare the new research section with `RESEARCH_BLOCK` in `scripts/build_cv.py`, update that wording for public use, and set `EXPECTED_RESEARCH_SHA256` to the fingerprint the build printed.

## Regenerating the share image

`assets/og-image.png` is a 1200 × 630 screenshot of `scripts/og-card.html`, taken at device scale 1 in the light theme while the local preview is running.
