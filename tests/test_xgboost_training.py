"""
Testes S3-01 — treino XGBoost e métricas.

Estratégia de testes
--------------------
  - Funções puras (split, métricas, URIs) sem AWS.
  - Treino real com XGBoost em dados sintéticos (importorskip se xgboost ausente).
  - boto3 e read_parquet mockados para testes de I/O S3.

Critérios validados
-------------------
  - Split 80/20 com random_state=42 reproduzível
  - RMSE/MAE logados e salvos em metrics.json
  - URI metrics/{ref_date}/metrics.json

Como executar
-------------
  python -m pytest tests/test_xgboost_training.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from schema_validation import FEATURE_COLUMNS, TARGET_COLUMN  # noqa: E402
from xgboost_training import (  # noqa: E402
    RANDOM_STATE,
    TEST_SIZE,
    build_xgboost_regressor,
    compute_regression_metrics,
    metrics_json_uri,
    read_features_parquet,
    save_metrics_json,
    split_features_target,
    split_train_validation,
    train_and_evaluate,
)


def _features_frame(rows: int = 20) -> pd.DataFrame:
    """DataFrame sintético com schema de features Parquet (S2-03)."""
    rng = np.random.default_rng(RANDOM_STATE)
    data = {column: rng.random(rows) for column in FEATURE_COLUMNS}
    data[TARGET_COLUMN] = rng.integers(1, 1000, size=rows)
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# URIs S3
# ---------------------------------------------------------------------------

def test_metrics_json_uri_from_raw_path() -> None:
    """Convenção de path: metrics/{ref_date}/metrics.json."""
    uri = metrics_json_uri(
        "s3://glue-b3-dev-s3-pipeline-303238378103/raw/day.csv",
        "2011-06-01",
    )

    assert uri == "s3://glue-b3-dev-s3-pipeline-303238378103/metrics/2011-06-01/metrics.json"


# ---------------------------------------------------------------------------
# Preparação X / y e split
# ---------------------------------------------------------------------------

def test_split_features_target_separates_x_and_y() -> None:
    """X contém só FEATURE_COLUMNS; y é a série cnt."""
    df = _features_frame(5)
    x, y = split_features_target(df)

    assert list(x.columns) == list(FEATURE_COLUMNS)
    assert len(y) == 5
    assert y.name == TARGET_COLUMN


def test_split_features_target_raises_on_missing_column() -> None:
    """Parquet corrompido/incompleto deve falhar cedo."""
    df = _features_frame(3).drop(columns=["temp"])

    with pytest.raises(ValueError, match="'temp'"):
        split_features_target(df)


def test_split_train_validation_uses_80_20_and_fixed_seed() -> None:
    """Critério S3-01: exatamente 80% treino, 20% validação com n=100."""
    df = _features_frame(100)
    x, y = split_features_target(df)

    x_train, x_val, y_train, y_val = split_train_validation(x, y)

    assert len(x_train) == 80
    assert len(x_val) == 20
    assert len(y_train) == 80
    assert len(y_val) == 20


def test_split_train_validation_is_reproducible() -> None:
    """Mesmo random_state → mesmas partições (reprodutibilidade)."""
    df = _features_frame(50)
    x, y = split_features_target(df)

    first = split_train_validation(x, y)
    second = split_train_validation(x, y)

    pd.testing.assert_frame_equal(first[0], second[0])
    pd.testing.assert_series_equal(first[3], second[3])


# ---------------------------------------------------------------------------
# Métricas e hiperparâmetros do modelo
# ---------------------------------------------------------------------------

def test_compute_regression_metrics_perfect_prediction() -> None:
    """Sanity check: predição perfeita → RMSE e MAE zero."""
    y = pd.Series([1.0, 2.0, 3.0])
    pred = np.array([1.0, 2.0, 3.0])

    scores = compute_regression_metrics(y, pred)

    assert scores["rmse"] == 0.0
    assert scores["mae"] == 0.0


def test_build_xgboost_regressor_has_basic_params() -> None:
    """Parâmetros básicos conforme story S3-01."""
    pytest.importorskip("xgboost")
    model = build_xgboost_regressor()

    assert model.n_estimators == 100
    assert model.max_depth == 6
    assert model.learning_rate == 0.1
    assert model.random_state == RANDOM_STATE


# ---------------------------------------------------------------------------
# I/O S3 (mockado)
# ---------------------------------------------------------------------------

@patch("xgboost_training.pd.read_parquet")
def test_read_features_parquet_uses_pyarrow(mock_read_parquet) -> None:
    """Leitura Parquet usa engine pyarrow (consistente com S2-03)."""
    expected = _features_frame(4)
    mock_read_parquet.return_value = expected

    result = read_features_parquet("s3://bucket/features/2011-06-01/features.parquet")

    mock_read_parquet.assert_called_once_with(
        "s3://bucket/features/2011-06-01/features.parquet",
        engine="pyarrow",
    )
    assert len(result) == 4


@patch("xgboost_training.boto3.client")
def test_save_metrics_json_writes_to_s3(mock_boto_client) -> None:
    """JSON enviado via put_object com ContentType application/json."""
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3
    payload = {"ref_date": "2011-06-01", "rmse": 10.5, "mae": 8.2}

    save_metrics_json(payload, "s3://my-bucket/metrics/2011-06-01/metrics.json")

    mock_s3.put_object.assert_called_once()
    call_kwargs = mock_s3.put_object.call_args.kwargs
    assert call_kwargs["Bucket"] == "my-bucket"
    assert call_kwargs["Key"] == "metrics/2011-06-01/metrics.json"
    assert call_kwargs["ContentType"] == "application/json"
    saved = json.loads(call_kwargs["Body"].decode("utf-8"))
    assert saved["rmse"] == 10.5


# ---------------------------------------------------------------------------
# Orquestração train_and_evaluate
# ---------------------------------------------------------------------------

@patch("xgboost_training.save_model_joblib")
@patch("xgboost_training.s3_object_exists", return_value=False)
@patch("xgboost_training.save_metrics_json")
@patch("xgboost_training.read_features_parquet")
def test_train_and_evaluate_end_to_end(mock_read, mock_save, _mock_exists, _mock_save_model) -> None:
    """Fluxo completo: treino real + métricas + URI de saída."""
    pytest.importorskip("xgboost")
    mock_read.return_value = _features_frame(30)

    metrics = train_and_evaluate(
        "s3://my-bucket/raw/day.csv",
        "2011-06-01",
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
    )

    assert metrics["ref_date"] == "2011-06-01"
    assert metrics["random_state"] == RANDOM_STATE
    assert metrics["test_size"] == TEST_SIZE
    assert metrics["n_samples"] == 30
    assert metrics["n_train"] == 24
    assert metrics["n_val"] == 6
    assert metrics["rmse"] >= 0.0
    assert metrics["mae"] >= 0.0
    assert metrics["metrics_json"] == "s3://my-bucket/metrics/2011-06-01/metrics.json"
    assert metrics["model_reused"] is False
    assert "model.pkl" in metrics["model_pkl"]
    mock_save.assert_called_once()


@patch("xgboost_training.save_model_joblib")
@patch("xgboost_training.s3_object_exists", return_value=False)
@patch("xgboost_training.read_features_parquet")
def test_train_and_evaluate_logs_rmse_mae(mock_read, _mock_exists, _mock_save_model, caplog) -> None:
    """Critério S3-01: RMSE e MAE aparecem no log CloudWatch."""
    pytest.importorskip("xgboost")
    mock_read.return_value = _features_frame(25)

    with caplog.at_level("INFO"):
        with patch("xgboost_training.save_metrics_json"):
            train_and_evaluate("s3://my-bucket/raw/day.csv", "2011-06-01")

    assert "RMSE=" in caplog.text
    assert "MAE=" in caplog.text


@patch("xgboost_training.read_features_parquet")
def test_train_and_evaluate_raises_when_too_few_rows(mock_read) -> None:
    """1 registro não permite split 80/20 — deve falhar com mensagem clara."""
    mock_read.return_value = _features_frame(1)

    with pytest.raises(ValueError, match="Insuficientes registros"):
        train_and_evaluate("s3://my-bucket/raw/day.csv", "2011-06-01")
