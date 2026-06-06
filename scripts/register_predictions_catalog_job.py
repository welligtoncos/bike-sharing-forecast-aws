"""
S4-01 — Glue Job: registrar tabela predictions no Glue Catalog.

Argumentos:
  --s3_input_path              URI S3 do day.csv (deriva bucket)
  --ref_date                   Particao ref_date (YYYY-MM-DD)
  --database_name              Database Glue (default: bike_sharing)
  --predictions_parquet_path   URI Parquet opcional (default: predictions/ref_date=.../)
"""

from __future__ import annotations

import logging
import sys

from awsglue.utils import getResolvedOptions

from glue_catalog_predictions import DATABASE_NAME_DEFAULT, register_predictions_table

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def _optional_arg(name: str) -> str | None:
    prefix = f"--{name}"
    for index, token in enumerate(sys.argv):
        if token == prefix and index + 1 < len(sys.argv):
            return sys.argv[index + 1]
    return None


def main() -> None:
    """Registra bike_sharing.predictions inferindo schema do Parquet."""
    args = getResolvedOptions(sys.argv, ["s3_input_path", "ref_date"])
    s3_input_path = args["s3_input_path"]
    ref_date = args["ref_date"]
    database_name = _optional_arg("database_name") or DATABASE_NAME_DEFAULT
    predictions_parquet_path = _optional_arg("predictions_parquet_path")

    logger.info("s3_input_path=%s", s3_input_path)
    logger.info("ref_date=%s", ref_date)
    logger.info("database_name=%s", database_name)

    result = register_predictions_table(
        s3_input_path,
        ref_date,
        database_name=database_name,
        predictions_parquet_path=predictions_parquet_path,
    )

    print(f"qualified_name: {result['qualified_name']}")
    print(f"ref_date: {result['ref_date']}")
    print(f"partition_location: {result['partition_location']}")
    print(f"predictions_parquet: {result['predictions_parquet']}")


if __name__ == "__main__":
    main()
