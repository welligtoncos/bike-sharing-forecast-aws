"""Testes S3-02 / S3-03 — model.pkl e inferencia."""

from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from xgboost_inference import generate_predictions_parquet  # noqa: E402
from xgboost_training import (  # noqa: E402
    model_pkl_uri,
    save_model_joblib,
    train_and_evaluate,
)


def test_model_pkl_uri_from_raw_path() -> None:
    uri = model_pkl_uri("s3://bucket/raw/day.csv", "2011-06-01")
    assert uri == "s3://bucket/models/2011-06-01/model.pkl"


@patch("xgboost_training.boto3.client")
def test_save_model_joblib_uploads_pkl(mock_boto_client) -> None:
    pytest.importorskip("xgboost")
    pytest.importorskip("joblib")
    from xgboost_training import build_xgboost_regressor

    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3
    model = build_xgboost_regressor()
    x = pd.DataFrame({"season": [1], "temp": [0.5], "hum": [0.4], "windspeed": [0.1], "weekday": [1]})
    model.fit(x, [100])

    save_model_joblib(model, "s3://my-bucket/models/2011-06-01/model.pkl")

    mock_s3.put_object.assert_called_once()
    kwargs = mock_s3.put_object.call_args.kwargs
    assert kwargs["Bucket"] == "my-bucket"
    assert kwargs["Key"] == "models/2011-06-01/model.pkl"
    assert len(kwargs["Body"]) > 0


@patch("xgboost_training.save_metrics_json")
@patch("xgboost_training.read_features_parquet")
@patch("xgboost_training.s3_object_exists")
@patch("xgboost_training.load_model_joblib")
@patch("xgboost_training.save_model_joblib")
def test_train_and_evaluate_reuses_existing_model(
    mock_save_model,
    mock_load_model,
    mock_exists,
    mock_read,
    mock_save_metrics,
) -> None:
    pytest.importorskip("xgboost")
    mock_exists.return_value = True
    mock_model = MagicMock()
    mock_model.predict.return_value = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    mock_load_model.return_value = mock_model
    mock_read.return_value = pd.DataFrame(
        {
            "season": [1] * 30,
            "temp": [0.5] * 30,
            "hum": [0.4] * 30,
            "windspeed": [0.1] * 30,
            "weekday": list(range(7)) * 4 + [1, 2],
            "cnt": list(range(30)),
        }
    )

    metrics = train_and_evaluate("s3://b/raw/day.csv", "2011-06-01")

    assert metrics["model_reused"] is True
    mock_load_model.assert_called_once()
    mock_save_model.assert_not_called()
    mock_model.fit.assert_not_called()


@patch("xgboost_inference.predictions_parquet_uri")
@patch("xgboost_inference.load_model_joblib")
@patch("xgboost_inference.s3_object_exists")
@patch("xgboost_inference.read_features_parquet")
@patch("xgboost_inference.process_day_csv")
def test_generate_predictions_parquet_clips_negatives(
    mock_process,
    mock_read_features,
    mock_exists,
    mock_load_model,
    mock_uri,
) -> None:
    mock_exists.return_value = True
    mock_process.return_value = pd.DataFrame(
        {
            "dteday": ["2011-06-01"],
            "cnt": [100],
            "season": [1],
            "temp": [0.5],
            "hum": [0.4],
            "windspeed": [0.1],
            "weekday": [3],
        }
    )
    mock_read_features.return_value = pd.DataFrame(
        {
            "season": [1],
            "temp": [0.5],
            "hum": [0.4],
            "windspeed": [0.1],
            "weekday": [3],
            "cnt": [100],
        }
    )
    model = mock_load_model.return_value
    model.predict.return_value = [-5.0]
    mock_uri.return_value = "s3://b/predictions/ref_date=2011-06-01/predictions.parquet"

    saved: list[pd.DataFrame] = []

    def capture_to_parquet(self, uri, **kwargs) -> None:
        saved.append(self.copy())

    with patch.object(pd.DataFrame, "to_parquet", capture_to_parquet):
        uri = generate_predictions_parquet("s3://b/raw/day.csv", "2011-06-01")

    assert uri.endswith("predictions.parquet")
    assert saved[0]["cnt_pred"].iloc[0] == 0.0


@patch("xgboost_inference.s3_object_exists")
def test_generate_predictions_requires_model(mock_exists) -> None:
    mock_exists.return_value = False

    with pytest.raises(ValueError, match="Modelo nao encontrado"):
        generate_predictions_parquet("s3://b/raw/day.csv", "2011-06-01")
