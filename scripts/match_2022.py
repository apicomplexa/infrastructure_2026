"""CLI entry point for the independent 2022 <-> v3 matcher.

The matcher itself is a library module (src/arkhinfra/match_2022.py) because
analysis/v3/eda-v3-validation.qmd imports it; this launcher only puts src/ on
sys.path so `pixi run match-2022` works from a plain checkout.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from arkhinfra.match_2022 import main  # noqa: E402

if __name__ == "__main__":
    main()
