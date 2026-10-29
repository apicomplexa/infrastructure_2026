"""Download a snapshot of Overture Maps Places around the three final-delivery cities.

Overture Places (CDLA-Permissive 2.0; AllThePlaces rows CC0) is the one open
POI layer independent of all three directories the export already uses: its
places theme carries **no OSM**, only Meta (Facebook pages), Foursquare and
AllThePlaces (chains' own websites).  It is read here once, by bounding box,
straight from the public S3 bucket with DuckDB, and written to
`data/raw_alter_overture/` -- a downloaded source like the licence registry,
treated as read-only afterwards.  Every place is kept, not only catering:
confirming that an object *exists* does not need Overture to agree on its kind.

    pixi run fetch-overture                          # the default release
    pixi run fetch-overture --release 2026-10-21.0   # a named release

The first source of each place is kept as `dataset` / `record_id` /
`update_time`; Meta rows are a weaker kind of evidence (the pages are not
maintained from Russia since 2022, and `operating_status` is empty), which the
matcher reports but does not discount.  A full pass takes ~2 minutes.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import duckdb  # noqa: E402

from arkhinfra.paths import RAW_OVERTURE  # noqa: E402

RELEASE = "2026-10-21.0"
# Архангельск, Северодвинск and Новодвинск together, with a margin.
BBOX = {"lon": (39.70, 40.90), "lat": (64.38, 64.73)}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--release", default=RELEASE)
    args = p.parse_args(argv)

    out = RAW_OVERTURE / f"overture_places_{args.release}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    c = duckdb.connect()
    c.sql("INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")
    (lo0, lo1), (la0, la1) = BBOX["lon"], BBOX["lat"]
    c.sql(f"""
        COPY (
          SELECT id, names.primary AS name, basic_category, taxonomy.primary AS category,
                 confidence, operating_status,
                 addresses[1].freeform AS address, addresses[1].locality AS locality,
                 sources[1].dataset AS dataset, sources[1].record_id AS record_id,
                 sources[1].update_time AS update_time,
                 array_to_string(list_transform(sources, lambda s: s.dataset), '|') AS datasets,
                 (bbox.ymin + bbox.ymax) / 2 AS lat, (bbox.xmin + bbox.xmax) / 2 AS lon
          FROM read_parquet('s3://overturemaps-us-west-2/release/{args.release}/theme=places/type=place/*',
                            hive_partitioning = 1)
          WHERE bbox.xmin BETWEEN {lo0} AND {lo1} AND bbox.ymin BETWEEN {la0} AND {la1}
        ) TO '{out}' (FORMAT parquet)""")
    n = c.sql(f"SELECT count(*), count(DISTINCT dataset) FROM '{out}'").fetchall()[0]
    print(f"wrote {out}  ({n[0]:,} places)")
    print(c.sql(f"SELECT dataset, count(*) n FROM '{out}' GROUP BY 1 ORDER BY 2 DESC"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
