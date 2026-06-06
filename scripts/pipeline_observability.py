"""
S4-03 — Métricas customizadas CloudWatch para observabilidade do pipeline.

Publica RMSE/MAE, breach de threshold e falhas de Glue Job para alarmes SNS.
"""

from __future__ import annotations

import logging
from typing import Any

import boto3

logger = logging.getLogger(__name__)

METRIC_RMSE = "RMSE"
METRIC_MAE = "MAE"
METRIC_RMSE_THRESHOLD_BREACHED = "RMSEThresholdBreached"
METRIC_GLUE_JOB_FAILURE = "GlueJobFailure"

DEFAULT_NAMESPACE = "glue-b3/dev/Pipeline"


def publish_training_metrics(
    *,
    namespace: str,
    ref_date: str,
    rmse: float,
    mae: float,
    rmse_threshold: float | None = None,
    cloudwatch_client: Any | None = None,
) -> bool:
    """
    Publica RMSE/MAE no CloudWatch e RMSEThresholdBreached se rmse > threshold.

    Returns:
        True se o threshold foi violado.
    """
    client = cloudwatch_client or boto3.client("cloudwatch")
    dimensions = [{"Name": "ref_date", "Value": ref_date}]

    metric_data: list[dict[str, Any]] = [
        {
            "MetricName": METRIC_RMSE,
            "Dimensions": dimensions,
            "Value": rmse,
            "Unit": "None",
        },
        {
            "MetricName": METRIC_MAE,
            "Dimensions": dimensions,
            "Value": mae,
            "Unit": "None",
        },
    ]

    breached = rmse_threshold is not None and rmse > rmse_threshold
    if breached:
        metric_data.append(
            {
                "MetricName": METRIC_RMSE_THRESHOLD_BREACHED,
                "Dimensions": dimensions,
                "Value": 1.0,
                "Unit": "Count",
            }
        )
        logger.warning(
            "RMSE %.4f excedeu threshold %.4f (ref_date=%s)",
            rmse,
            rmse_threshold,
            ref_date,
        )

    client.put_metric_data(Namespace=namespace, MetricData=metric_data)
    logger.info(
        "Metricas CloudWatch publicadas (namespace=%s, ref_date=%s, rmse=%.4f)",
        namespace,
        ref_date,
        rmse,
    )
    return breached


def publish_glue_job_failure(
    *,
    namespace: str,
    job_name: str,
    ref_date: str | None = None,
    cloudwatch_client: Any | None = None,
) -> None:
    """Publica GlueJobFailure=1 para alarme CloudWatch."""
    client = cloudwatch_client or boto3.client("cloudwatch")
    dimensions = [{"Name": "JobName", "Value": job_name}]
    if ref_date:
        dimensions.append({"Name": "ref_date", "Value": ref_date})

    client.put_metric_data(
        Namespace=namespace,
        MetricData=[
            {
                "MetricName": METRIC_GLUE_JOB_FAILURE,
                "Dimensions": dimensions,
                "Value": 1.0,
                "Unit": "Count",
            }
        ],
    )
    logger.error("GlueJobFailure publicado (job=%s, ref_date=%s)", job_name, ref_date)


def parse_rmse_threshold(value: str | None) -> float | None:
    """Converte argumento Glue --rmse_threshold; vazio desabilita breach."""
    if value is None or str(value).strip() == "":
        return None
    return float(value)
