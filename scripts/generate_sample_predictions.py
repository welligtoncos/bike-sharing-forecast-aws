"""
Gera predictions.parquet de amostra no S3 (dev / validacao S4-01).

Uso local:
  python scripts/generate_sample_predictions.py \\
    --s3_input_path s3://bucket/raw/day.csv \\
    --ref_date 2011-06-01
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sample_predictions import generate_sample_predictions_parquet

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera predictions.parquet de amostra no S3")
    parser.add_argument("--s3_input_path", required=True, help="s3://bucket/raw/day.csv")
    parser.add_argument("--ref_date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()

    uri = generate_sample_predictions_parquet(args.s3_input_path, args.ref_date)
    print(f"predictions_parquet: {uri}")


if __name__ == "__main__":
    main()
