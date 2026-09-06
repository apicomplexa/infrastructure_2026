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
         "analysis/v3/eda-v3-basecheck-ru.qmd", "analysis/v4/eda-v4-ru.qmd"]

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

# The fourth-delivery twin (analysis/v4/eda-v4-ru.qmd).  Triple-quoted because
# several of these expressions contain both quote characters themselves.
INLINE.update({
    '''`{python} f"{n_sites / len(v3) * 100:.1f}"`''':
        '''`{python} f"{n_sites / len(v3) * 100:.1f}".replace(".", ",")`''',
    '''`{python} f"{osm_only_alc * 100:.1f}"`''':
        '''`{python} f"{osm_only_alc * 100:.1f}".replace(".", ",")`''',
    '''`{python} f"{ratio_v3:.1f}"`''':
        '''`{python} f"{ratio_v3:.1f}".replace(".", ",")`''',
    '''`{python} f"{ratio_v4:.2f}"`''':
        '''`{python} f"{ratio_v4:.2f}".replace(".", ",")`''',
    '''`{python} f"{sp3:.1f}"`''':
        '''`{python} f"{sp3:.1f}".replace(".", ",")`''',
    '''`{python} f"{sp4:.1f}"`''':
        '''`{python} f"{sp4:.1f}".replace(".", ",")`''',
    '''`{python} f"{okr['Ratio vs v4'].min():.2f}"`''':
        '''`{python} f"{okr['Ratio vs v4'].min():.2f}".replace(".", ",")`''',
    '''`{python} f"{okr['Ratio vs v4'].max():.2f}"`''':
        '''`{python} f"{okr['Ratio vs v4'].max():.2f}".replace(".", ",")`''',
    '''`{python} f"{raw_t['match_distance_meters'].isna().mean() * 100:.1f}"`''':
        '''`{python} f"{raw_t['match_distance_meters'].isna().mean() * 100:.1f}".replace(".", ",")`''',
    '''`{python} f"{raw_a['match_distance_meters'].isna().mean() * 100:.1f}"`''':
        '''`{python} f"{raw_a['match_distance_meters'].isna().mean() * 100:.1f}".replace(".", ",")`''',
    '''`{python} f"{raw_v3['match_distance_meters'].isna().mean() * 100:.1f}"`''':
        '''`{python} f"{raw_v3['match_distance_meters'].isna().mean() * 100:.1f}".replace(".", ",")`''',
    '''`{python} f"{rev3_50}"`''':
        '''`{python} f"{rev3_50}".replace(".", ",")`''',
    '''`{python} f"{rev4_50}"`''':
        '''`{python} f"{rev4_50}".replace(".", ",")`''',
    '''`{python} f"{rev4_100}"`''':
        '''`{python} f"{rev4_100}".replace(".", ",")`''',
    '''`{python} f"{n_tob:,}"`''':
        '''`{python} f"{n_tob:,}".replace(",", " ")`''',
    '''`{python} f"{n_alc:,}"`''':
        '''`{python} f"{n_alc:,}".replace(",", " ")`''',
    '''`{python} f"{n_sites:,}"`''':
        '''`{python} f"{n_sites:,}".replace(",", " ")`''',
    '''`{python} f"{n_tob + n_alc:,}"`''':
        '''`{python} f"{n_tob + n_alc:,}".replace(",", " ")`''',
    '''`{python} r_v3_al`''':
        '''`{python} r_v3_al.replace(".", ",")`''',
    '''`{python} r_v3_tb`''':
        '''`{python} r_v3_tb.replace(".", ",")`''',
    '''`{python} r_v4_al`''':
        '''`{python} r_v4_al.replace(".", ",")`''',
    '''`{python} r_v4_tb`''':
        '''`{python} r_v4_tb.replace(".", ",")`''',
})

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
