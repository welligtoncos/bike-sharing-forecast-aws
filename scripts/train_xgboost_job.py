"""
S3-01 / S4-03 — Glue Job: treino XGBoost com metricas CloudWatch.

Argumentos adicionais (S4-03):
  --rmse_threshold         RMSE maximo (Step Functions / alarme)
  --cloudwatch_namespace   Namespace custom metric (default glue-b3/dev/Pipeline)
"""

from __future__ import annotations

import logging
import sys

from awsglue.utils import getResolvedOptions

from pipeline_observability import (
    DEFAULT_NAMESPACE,
    parse_rmse_threshold,
    publish_glue_job_failure,
)
from xgboost_training import train_and_evaluate_with_observability

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

JOB_NAME = "train_xgboost"


def _optional_arg(name: str) -> str | None:
    prefix = f"--{name}"
    for index, token in enumerate(sys.argv):
        if token == prefix and index + 1 < len(sys.argv):
            return sys.argv[index + 1]
    return None


def main() -> None:
    """Treina modelo, publica metricas CloudWatch e trata falhas para alarmes."""
    args = getResolvedOptions(sys.argv, ["s3_input_path", "ref_date"])
    s3_input_path = args["s3_input_path"]
    ref_date = args["ref_date"]
    rmse_threshold = parse_rmse_threshold(_optional_arg("rmse_threshold"))
    namespace = _optional_arg("cloudwatch_namespace") or DEFAULT_NAMESPACE
    force_retrain = (_optional_arg("force_retrain") or "false").lower() in ("1", "true", "yes")

    logger.info("s3_input_path=%s", s3_input_path)
    logger.info("ref_date=%s", ref_date)
    logger.info("rmse_threshold=%s", rmse_threshold)
    logger.info("cloudwatch_namespace=%s", namespace)
    logger.info("force_retrain=%s", force_retrain)

    try:
        metrics = train_and_evaluate_with_observability(
            s3_input_path,
            ref_date,
            rmse_threshold=rmse_threshold,
            cloudwatch_namespace=namespace,
            force_retrain=force_retrain,
        )
    except Exception:
        publish_glue_job_failure(
            namespace=namespace,
            job_name=JOB_NAME,
            ref_date=ref_date,
        )
        raise

    print(f"s3_input_path: {s3_input_path}")
    print(f"ref_date: {ref_date}")
    print(f"rmse: {metrics['rmse']:.4f}")
    print(f"mae: {metrics['mae']:.4f}")
    print(f"rmse_threshold_breached: {metrics['rmse_threshold_breached']}")
    print(f"model_reused: {metrics['model_reused']}")
    print(f"model_pkl: {metrics['model_pkl']}")
    print(f"metrics_json: {metrics['metrics_json']}")


if __name__ == "__main__":
    main()
