"""Download a snapshot of Foursquare OS Places around the three final-delivery cities.

FSQ OS Places (Apache 2.0) is the full Foursquare open layer; Overture carries
only a few hundred of its rows here.  Since 2025-10 it is published as a
**gated** Hugging Face dataset (`foursquare/fsq-os-places`), so the run needs
a Hugging Face account that has accepted the dataset's terms and a read token
saved where `huggingface_hub` keeps it (`hf auth login` writes
`~/.cache/huggingface/token`); DuckDB picks it up from there or from
`HF_TOKEN`.  The token is never written into this repository.

    pixi run fetch-foursquare                        # the default release
    pixi run fetch-foursquare --release 2026-10-15   # a named release

Only the bounding box is read: DuckDB pushes the latitude/longitude filter
into the parquet row-group statistics, so ~12 GB of release is not downloaded
whole.  Written to `data/raw_alter_foursquare/`, read-only afterwards.
`date_closed` is kept -- a place Foursquare marks closed is not evidence of
existence.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import duckdb  # noqa: E402

from arkhinfra.paths import RAW_FOURSQUARE  # noqa: E402

RELEASE = "2026-10-15"
# Same box as fetch_overture.py: Архангельск, Северодвинск, Новодвинск.
BBOX = {"lon": (39.70, 40.90), "lat": (64.38, 64.73)}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--release", default=RELEASE)
    args = p.parse_args(argv)

    out = RAW_FOURSQUARE / f"fsq_places_{args.release}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    c = duckdb.connect()
    c.sql("INSTALL httpfs; LOAD httpfs;")
    c.sql("CREATE SECRET hf (TYPE huggingface, PROVIDER credential_chain)")
    (lo0, lo1), (la0, la1) = BBOX["lon"], BBOX["lat"]
    src = f"hf://datasets/foursquare/fsq-os-places/release/dt={args.release}/places/parquet/*.parquet"
    c.sql(f"""
        COPY (
          SELECT fsq_place_id, name, latitude AS lat, longitude AS lon,
                 address, locality, region, postcode,
                 date_created, date_refreshed, date_closed,
                 tel, website, instagram,
                 array_to_string(fsq_category_labels, '|') AS categories
          FROM read_parquet('{src}')
          WHERE longitude BETWEEN {lo0} AND {lo1} AND latitude BETWEEN {la0} AND {la1}
        ) TO '{out}' (FORMAT parquet)""")
    n, closed = c.sql(f"SELECT count(*), count(date_closed) FROM '{out}'").fetchall()[0]
    print(f"wrote {out}  ({n:,} places, {closed:,} marked closed)")
    print(c.sql(f"SELECT locality, count(*) n FROM '{out}' GROUP BY 1 ORDER BY 2 DESC LIMIT 10"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
