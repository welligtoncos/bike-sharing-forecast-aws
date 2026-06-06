"""Testes S4-03 — metricas CloudWatch do pipeline."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from pipeline_observability import (  # noqa: E402
    METRIC_GLUE_JOB_FAILURE,
    METRIC_RMSE,
    METRIC_RMSE_THRESHOLD_BREACHED,
    parse_rmse_threshold,
    publish_glue_job_failure,
    publish_training_metrics,
)


def test_parse_rmse_threshold() -> None:
    assert parse_rmse_threshold("700") == 700.0
    assert parse_rmse_threshold(None) is None
    assert parse_rmse_threshold("") is None


def test_publish_training_metrics_sends_rmse_and_mae() -> None:
    client = MagicMock()

    breached = publish_training_metrics(
        namespace="glue-b3/dev/Pipeline",
        ref_date="2011-06-01",
        rmse=500.0,
        mae=400.0,
        rmse_threshold=700.0,
        cloudwatch_client=client,
    )

    assert breached is False
    client.put_metric_data.assert_called_once()
    names = {m["MetricName"] for m in client.put_metric_data.call_args.kwargs["MetricData"]}
    assert names == {METRIC_RMSE, "MAE"}


def test_publish_training_metrics_breach() -> None:
    client = MagicMock()

    breached = publish_training_metrics(
        namespace="glue-b3/dev/Pipeline",
        ref_date="2011-06-01",
        rmse=800.0,
        mae=600.0,
        rmse_threshold=700.0,
        cloudwatch_client=client,
    )

    assert breached is True
    names = {m["MetricName"] for m in client.put_metric_data.call_args.kwargs["MetricData"]}
    assert METRIC_RMSE_THRESHOLD_BREACHED in names


def test_publish_glue_job_failure() -> None:
    client = MagicMock()

    publish_glue_job_failure(
        namespace="glue-b3/dev/Pipeline",
        job_name="train_xgboost",
        ref_date="2011-06-01",
        cloudwatch_client=client,
    )

    metric = client.put_metric_data.call_args.kwargs["MetricData"][0]
    assert metric["MetricName"] == METRIC_GLUE_JOB_FAILURE
    assert metric["Value"] == 1.0


@patch("pipeline_observability.publish_training_metrics")
@patch("xgboost_training.train_and_evaluate")
def test_train_and_evaluate_with_observability(mock_train, mock_publish) -> None:
    from xgboost_training import train_and_evaluate_with_observability  # noqa: WPS433

    mock_train.return_value = {"rmse": 628.9, "mae": 428.0, "metrics_json": "s3://b/m.json"}
    mock_publish.return_value = False

    result = train_and_evaluate_with_observability(
        "s3://b/raw/day.csv",
        "2011-06-01",
        rmse_threshold=700.0,
        cloudwatch_namespace="glue-b3/dev/Pipeline",
    )

    mock_publish.assert_called_once()
    assert result["rmse_threshold_breached"] is False
    assert result["cloudwatch_namespace"] == "glue-b3/dev/Pipeline"
