"""Normalise number formatting in the Russian twins to Russian convention.

Run from the repo root:  pixi run python scripts/ru_numfmt.py
Idempotent -- safe to re-run after scripts/build_ru_v3.py regenerates a twin.

Decimal comma and a thin space for thousands, applied to prose and to figure /
table captions only.  Lines inside {python} cells are left untouched, except for
the inline `{python} ...` expressions that appear in running prose -- those are
prose too, and they currently emit English-formatted numbers.
"""
import io
import re
import sys

FILES = ["analysis/v3/eda-v3-ru.qmd", "analysis/v3/eda-v3-validation-ru.qmd",
         "analysis/v3/eda-v3-basecheck-ru.qmd"]

# Inline expressions in prose: wrap so the emitted number reads as Russian.
INLINE = {
    '`{python} f"{np.median(lin3):.2f}"`':
        '`{python} f"{np.median(lin3):.2f}".replace(".", ",")`',
    '`{python} f"{n_obj:,}"`':
        '`{python} f"{n_obj:,}".replace(",", " ")`',
    '`{python} f"{n_base:,}"`':
        '`{python} f"{n_base:,}".replace(",", " ")`',
    '`{python} f"{len(three):,}"`':
        '`{python} f"{len(three):,}".replace(",", " ")`',
    '`{python} f"{R_LOCAL:.1f}"`':
        '`{python} f"{R_LOCAL:.1f}".replace(".", ",")`',
    '`{python} f"{R_VENDOR:.1f}"`':
        '`{python} f"{R_VENDOR:.1f}".replace(".", ",")`',
    '`{python} f"{len(ref_local) - len(ka):,}"`':
        '`{python} f"{len(ref_local) - len(ka):,}".replace(",", " ")`',
    '`{python} f"{len(ven_raw) - len(kb):,}"`':
        '`{python} f"{len(ven_raw) - len(kb):,}".replace(",", " ")`',
    '`{python} f"{rate_three:.1f}"`':
        '`{python} f"{rate_three:.1f}".replace(".", ",")`',
    '`{python} f"{STRONG:.2f}"`':
        '`{python} f"{STRONG:.2f}".replace(".", ",")`',
    '`{python} f"{WEAK:.2f}"`':
        '`{python} f"{WEAK:.2f}".replace(".", ",")`',
}

# A bare decimal number, not part of a version/path/identifier.
DEC = re.compile(r"(?<![\w.,/-])(\d{1,3})\.(\d{1,3})(?![\d.])")
# English thousands separator inside prose, e.g. 1,753 -> 1 753.
THOU = re.compile(r"(?<![\w,.])(\d{1,3})(?:,(\d{3}))+(?![\d,])")


def fix_thousands(m):
    return m.group(0).replace(",", " ")


def convert(text):
    text = THOU.sub(fix_thousands, text)
    return DEC.sub(lambda m: f"{m.group(1)},{m.group(2)}", text)


def protect(line):
    """Split a line into (prose, code) spans so backticked code is untouched."""
    parts = re.split(r"(`[^`]*`)", line)
    return "".join(p if p.startswith("`") else convert(p) for p in parts)


def main():
    for path in FILES:
        src = io.open(path, encoding="utf-8").read()
        for old, new in INLINE.items():
            src = src.replace(old, new)

        out, incode, changed = [], False, 0
        fm = 0          # YAML front matter is never touched: 7.2 must stay 7.2
        for line in src.split("\n"):
            if fm < 2:
                if line.strip() == "---":
                    fm += 1
                out.append(line)
                continue
            if line.startswith("```"):
                incode = not incode
                out.append(line)
                continue
            cap = re.match(r'^(# \| (?:fig|tbl)-cap: ")(.*)("\s*)$', line)
            if incode and cap:
                new = cap.group(1) + protect(cap.group(2)) + cap.group(3)
            elif incode:
                new = line
            else:
                new = protect(line)
            changed += new != line
            out.append(new)

        io.open(path, "w", encoding="utf-8").write("\n".join(out))
        print(f"{path}: {changed} lines renumbered")
    return 0


if __name__ == "__main__":
    sys.exit(main())
