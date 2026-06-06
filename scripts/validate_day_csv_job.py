"""
S2-01 / S2-02 — Glue Job Python Shell: validacao e filtro do day.csv.

Argumentos:
  --s3_input_path  URI S3 do day.csv (ex.: s3://bucket/raw/day.csv)
  --ref_date       Data de referencia YYYY-MM-DD (filtra dteday por mes/ano)
"""

from __future__ import annotations

import logging
import sys

from awsglue.utils import getResolvedOptions

from schema_validation import process_day_csv

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    args = getResolvedOptions(sys.argv, ["s3_input_path", "ref_date"])
    s3_input_path = args["s3_input_path"]
    ref_date = args["ref_date"]

    logger.info("s3_input_path=%s", s3_input_path)
    logger.info("ref_date=%s", ref_date)

    df = process_day_csv(s3_input_path, ref_date)

    print(f"s3_input_path: {s3_input_path}")
    print(f"ref_date: {ref_date}")

    if df is None:
        print("status: empty_no_records")
        return

    print(f"shape: {df.shape}")
    print(f"filtered_rows: {len(df)}")
    print(f"columns: {list(df.columns)}")


if __name__ == "__main__":
    main()
