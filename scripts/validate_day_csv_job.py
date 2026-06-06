"""
S2-01 — Glue Job Python Shell: validacao de schema do day.csv.

Argumentos:
  --s3_input_path  URI S3 do day.csv (ex.: s3://bucket/raw/day.csv)
"""

from __future__ import annotations

import logging
import sys

from awsglue.utils import getResolvedOptions

from schema_validation import load_and_validate_day_csv

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    args = getResolvedOptions(sys.argv, ["s3_input_path"])
    s3_input_path = args["s3_input_path"]

    logger.info("s3_input_path=%s", s3_input_path)

    df = load_and_validate_day_csv(s3_input_path)

    print(f"s3_input_path: {s3_input_path}")
    print(f"shape: {df.shape}")
    print(f"columns: {list(df.columns)}")


if __name__ == "__main__":
    main()
