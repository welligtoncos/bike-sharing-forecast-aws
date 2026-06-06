"""
S3-03 — Glue Job: inferência XGBoost → predictions.parquet.

Pré-requisito: job train-xgboost (model.pkl) e validate-day-csv (features).
"""

from __future__ import annotations

import logging
import sys

from awsglue.utils import getResolvedOptions

from pipeline_observability import DEFAULT_NAMESPACE, publish_glue_job_failure
from xgboost_inference import generate_predictions_parquet

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

JOB_NAME = "predict_xgboost"


def main() -> None:
    args = getResolvedOptions(sys.argv, ["s3_input_path", "ref_date"])
    s3_input_path = args["s3_input_path"]
    ref_date = args["ref_date"]

    logger.info("s3_input_path=%s", s3_input_path)
    logger.info("ref_date=%s", ref_date)

    try:
        output_uri = generate_predictions_parquet(s3_input_path, ref_date)
    except Exception:
        publish_glue_job_failure(
            namespace=DEFAULT_NAMESPACE,
            job_name=JOB_NAME,
            ref_date=ref_date,
        )
        raise

    print(f"s3_input_path: {s3_input_path}")
    print(f"ref_date: {ref_date}")
    print(f"predictions_parquet: {output_uri}")


if __name__ == "__main__":
    main()
