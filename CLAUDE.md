# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Data + exploratory analysis for a study of urban-infrastructure distribution in
Arkhangelsk (health-supporting infrastructure vs. health risk factors). Not an
application — a small analysis repo. Background is in `docs/` and `README.md`.

## Environment & commands

Dependencies are managed with **pixi** (conda-forge). There is no system Python —
always run tools through pixi:

- `pixi install` — create the env from `pixi.lock`
- `pixi run eda` — render `analysis/eda.qmd` → `analysis/eda.pdf` (Quarto + XeLaTeX)
- `pixi run profile` — quick dataset profile
- `pixi run python <script>` — run any Python in the env

PDF rendering needs a system LaTeX install (built with MiKTeX on Windows).

## Data conventions

- Source data lives in `data/raw/` and is **read-only** — never modify it in place;
  write derived files elsewhere (e.g. a `data/processed/` you create).
- The main CSV is **semicolon-delimited, UTF-8 with BOM**. Read it as:
  `pd.read_csv(path, sep=";", encoding="utf-8-sig", low_memory=False)`.
- Category/type/district values are in **Russian**. The Windows console mangles
  Cyrillic on stdout — write Cyrillic output to a UTF-8 file and read it back
  rather than trusting terminal echo.
- Deliverable reports are in **English**; map Russian category/district names to
  English for report labels (see the dicts in `analysis/eda.qmd`).

## Analysis / plotting notes

- Charts embed in the PDF as images, so keep Cyrillic figure labels in a font
  with Cyrillic coverage — **DejaVu Sans** (matplotlib default) works.
- Body text and LaTeX tables use the `Arial` main font (set in the qmd front
  matter) for Cyrillic; the large title font is serif and lacks Cyrillic, so
  keep the `title`/`subtitle` ASCII-only.

## Known data caveat

District (`district_orig`) assignment in the 2026 export is skewed — ~71% of
objects fall into one okrug (Oktyabrsky). Treat district-level results as
provisional until the export's okrug-assignment step is re-validated.
