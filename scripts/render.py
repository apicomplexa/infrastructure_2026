"""Render reports from analysis/<delivery>/*.qmd to reports/<delivery>/*.pdf.

One entry point instead of a pixi task per PDF.  A report is named by its
source's stem; every analysis/*/*.qmd is a report, so a new one needs no task.
The two health-subset PDFs of the first delivery are the same sources rendered
with `-P dataset:health` (see VARIANTS).

    pixi run render                      # list the reports
    pixi run render eda-v4 eda-v4-ru     # named reports
    pixi run render v3                   # every report of one delivery
    pixi run render v3 --lang ru         # ... the Russian twins only
    pixi run render all                  # everything
    pixi run render v1 -n                # print the quarto commands, run nothing

Stops at the first failed render.  The rendered v3 reports carry the old
recoder's numbers on purpose (CLAUDE.md, the taxonomy re-cut): `all` and `v3`
re-render them, so name them only when that is what you mean.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from arkhinfra import paths  # noqa: E402

ANALYSIS = paths.ROOT / "analysis"

# Extra PDFs rendered from an existing source: name -> (source stem, quarto -P).
VARIANTS = {
    "eda-health": ("eda", "dataset:health"),
    "eda-health-ru": ("eda-ru", "dataset:health"),
}


def reports() -> dict[str, tuple[Path, str | None]]:
    """Every report name -> (its .qmd, the -P parameter or None), by delivery."""
    out = {}
    for qmd in sorted(ANALYSIS.glob("*/*.qmd")):
        out[qmd.stem] = (qmd, None)
    for name, (stem, param) in VARIANTS.items():
        if stem in out:
            out[name] = (out[stem][0], param)
    return dict(sorted(out.items(), key=lambda kv: (kv[1][0].parent.name, kv[0])))


def is_ru(name: str) -> bool:
    return name.endswith("-ru")


def select(selectors: list[str], lang: str | None) -> list[str]:
    known = reports()
    groups = {qmd.parent.name for qmd, _ in known.values()}
    chosen = []
    for sel in selectors:
        if sel == "all":
            hits = list(known)
        elif sel in groups:
            hits = [n for n, (qmd, _) in known.items() if qmd.parent.name == sel]
        elif sel in known:
            hits = [sel]
        else:
            sys.exit(f"unknown report or delivery: {sel!r} (run without arguments for the list)")
        chosen += [h for h in hits if h not in chosen]
    if lang:
        chosen = [n for n in chosen if is_ru(n) == (lang == "ru")]
    return chosen


def render(name: str, dry_run: bool) -> None:
    qmd, param = reports()[name]
    out_dir = paths.REPORTS / qmd.parent.name
    cmd = ["quarto", "render", str(qmd.relative_to(paths.ROOT)), "--to", "pdf",
           "--output-dir", os.path.relpath(out_dir, qmd.parent)]
    if param:
        cmd += ["-P", param]
    print("$", " ".join(cmd), flush=True)
    if dry_run:
        return
    if name == qmd.stem:
        subprocess.run(cmd, cwd=paths.ROOT, check=True)
    else:
        # A variant: quarto names the PDF after the source, so the source's own
        # PDF is set aside for the render and put back after it.
        own, aside = out_dir / f"{qmd.stem}.pdf", out_dir / f".{qmd.stem}.pdf.aside"
        if own.exists():
            own.replace(aside)
        try:
            subprocess.run(cmd, cwd=paths.ROOT, check=True)
            own.replace(out_dir / f"{name}.pdf")
        finally:
            if aside.exists():
                aside.replace(own)
    print(f"-> {(out_dir / f'{name}.pdf').relative_to(paths.ROOT)}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("targets", nargs="*", help="report names, delivery directories, or 'all'")
    ap.add_argument("--lang", choices=["en", "ru"], help="keep only English or only Russian reports")
    ap.add_argument("-n", "--dry-run", action="store_true", help="print the commands only")
    args = ap.parse_args()

    if not args.targets:
        for name, (qmd, param) in reports().items():
            src = qmd.relative_to(paths.ROOT)
            print(f"{name:24} {src}" + (f"  -P {param}" if param else ""))
        return
    names = select(args.targets, args.lang)
    try:
        for name in names:
            render(name, args.dry_run)
    except subprocess.CalledProcessError as e:
        sys.exit(f"render failed ({e.returncode}): {name}")


if __name__ == "__main__":
    main()
