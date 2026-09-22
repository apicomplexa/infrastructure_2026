# licmatch

Address-level record linkage between an object export and a licence register,
for Russian addresses.

Two sources describe the same door in different words; one of them names a
licence *holder* rather than a *shop*; half of one side carries no usable
coordinate; and the result has to be defensible line by line rather than merely
plausible in aggregate. That is the whole problem this package solves.

The methodology — what the rule does, why each number is what it is, how it was
checked, and which readings of the result are forbidden — is
[docs/METHODOLOGY.md](docs/METHODOLOGY.md) (in Russian).

## Why it is a package

It was extracted from `src/arkhinfra/v4_egais.py`, where the rule and one
study's column names lived together. Split out, it gains three things:

* it is **testable without the study's data** — 48 unit tests, no fixtures
  larger than four rows;
* the study-specific half shrinks to adapters, output columns and the domain
  reading of a match, which is what a reviewer should be arguing about;
* it can be lifted into another project, or into a git submodule, unchanged.

Extraction was verified byte-for-byte: `pixi run match-egais-v4` writes exactly
the files it wrote before.

## Use

```python
import licmatch as lm

city = lm.home_city_re("Архангельск")

objects = lm.side(
    [lm.parse_address_line(v, city) for v in export["address"]],
    [lm.fascia_name(v) for v in export["name"]],
    export["lat"], export["lon"],
)
register = lm.side(
    [lm.parse_address_fields(s, h, city) for s, h in registry[["street", "house"]].values],
    [lm.holder_name(v) for v in registry["holder"]],
    registry["lat"], registry["lon"],
)

scores = lm.score_matrix(objects, register, lm.DEFAULTS)
sel = lm.select(scores, lm.DEFAULTS,
                prefer=registry["in_force"].to_numpy(bool),
                keys=registry["licence_no"],
                groups={"matched": None, "active": registry["in_force"].to_numpy(bool)})

sel.hit                      # matched at all
sel.take(registry["licence_no"])   # the chosen licence per object
sel.counts["active"]         # distinct licences in force at the address
sel.joined("matched")        # "L-1; L-2"
```

`side()` is the only interface between a source and the rule: whatever the
source's column names, dialect or file format, an adapter parses it into
`Toponym`s and name keys, and nothing downstream can tell the two sides apart.

## Layout

| file | what is in it |
| --- | --- |
| `text.py` | folding, light Russian stemming |
| `toponym.py` | address parsing, the `Toponym`, the address term |
| `names.py` | holder / fascia normalisation, the operator→fascia aliases |
| `scoring.py` | `MatchParams`, the pair formula, the dense matrix, admission |
| `select.py` | choice, preference, distinct-key tallies, reverse coverage |
| `geo.py` | haversine |

## Install

The host repository vendors it: `arkhinfra.paths.ensure_licmatch_path()` puts
`packages/licmatch/src` on `sys.path`, so nothing needs installing and the
reports' byte-identical setup cell stays untouched.

To install it into an environment instead:

```
pip install -e packages/licmatch
```

Requires Python ≥ 3.11, `numpy`, `pandas`, `rapidfuzz`.

## Tests

```
pixi run licmatch-test                    # from the repository root
python packages/licmatch/run_tests.py     # anywhere
```

stdlib `unittest`, so the suite runs wherever the package is vendored. The test
that matters most is `test_scoring.py::TestMatrixMatchesFormula`: the dense
matrix is an optimisation of `pair_score()`, and an optimisation that quietly
disagrees with its definition is the defect class the suite exists to catch.

## Turning it into a git submodule

The package is already self-contained — no import reaches outside it. To publish
it separately:

```
git subtree split --prefix=packages/licmatch -b licmatch-split
# push that branch to a new repository, then in the host repo:
git rm -r packages/licmatch
git submodule add <url> packages/licmatch
```

Nothing in the host repository has to change: `ensure_licmatch_path()` points at
the same path either way.
