"""Testes — sample predictions (dev S4-01)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from sample_predictions import generate_sample_predictions_parquet  # noqa: E402


@patch("sample_predictions.predictions_parquet_uri")
@patch("sample_predictions.build_xgboost_regressor")
@patch("sample_predictions.read_features_parquet")
@patch("sample_predictions.process_day_csv")
def test_generate_sample_predictions_parquet(
    mock_process,
    mock_read_features,
    mock_build_model,
    mock_uri,
) -> None:
    pytest.importorskip("xgboost")
    mock_process.return_value = pd.DataFrame(
        {
            "dteday": ["2011-06-01", "2011-06-02"],
            "cnt": [100, 200],
            "season": [1, 1],
            "temp": [0.5, 0.6],
            "hum": [0.4, 0.5],
            "windspeed": [0.1, 0.2],
            "weekday": [3, 4],
        }
    )
    mock_read_features.return_value = pd.DataFrame(
        {
            "season": [1, 1],
            "temp": [0.5, 0.6],
            "hum": [0.4, 0.5],
            "windspeed": [0.1, 0.2],
            "weekday": [3, 4],
            "cnt": [100, 200],
        }
    )
    model = mock_build_model.return_value
    model.predict.return_value = [105.0, 195.0]
    mock_uri.return_value = "s3://b/predictions/ref_date=2011-06-01/predictions.parquet"

    saved_frames: list[pd.DataFrame] = []

    def capture_to_parquet(self, uri, **kwargs) -> None:
        saved_frames.append(self.copy())

    with patch.object(pd.DataFrame, "to_parquet", capture_to_parquet):
        uri = generate_sample_predictions_parquet("s3://b/raw/day.csv", "2011-06-01")

    assert uri == "s3://b/predictions/ref_date=2011-06-01/predictions.parquet"
    assert len(saved_frames) == 1
    assert list(saved_frames[0].columns) == ["dteday", "cnt_real", "cnt_pred"]
    assert len(saved_frames[0]) == 2
