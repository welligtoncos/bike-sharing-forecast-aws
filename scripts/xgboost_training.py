"""
S3-01 — Treino XGBoost de regressão a partir de features.parquet no S3.

Propósito
---------
Lê o Parquet gerado pelo S2-03, separa features (X) e target (y=cnt),
treina um XGBRegressor e avalia RMSE/MAE no conjunto de validação.

Critérios de aceite
-------------------
  - Split 80/20 com random_state fixo (reprodutibilidade)
  - RMSE e MAE logados no CloudWatch (via logger.info)
  - Métricas persistidas em s3://{bucket}/metrics/{ref_date}/metrics.json

Dependências Glue
-----------------
  xgboost, scikit-learn, pyarrow, s3fs (via additional-python-modules)
  schema_validation.py (via extra-py-files — reutiliza FEATURE_COLUMNS e URI helper)
"""

from __future__ import annotations

import json
import logging
from typing import Any

import boto3
import numpy as np
import pandas as pd
from botocore.exceptions import ClientError
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor

from schema_validation import FEATURE_COLUMNS, TARGET_COLUMN, features_parquet_uri

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hiperparâmetros de split e reprodutibilidade (critério de aceite S3-01)
# ---------------------------------------------------------------------------

RANDOM_STATE = 42   # Seed fixa — mesmo split em re-execuções
TEST_SIZE = 0.2     # 20% validação, 80% treino
METRICS_JSON_NAME = "metrics.json"
MODEL_PKL_NAME = "model.pkl"


# ---------------------------------------------------------------------------
# Helpers de URI S3
# ---------------------------------------------------------------------------

def metrics_json_uri(s3_input_path: str, ref_date: str) -> str:
    """
    Monta URI das métricas a partir do path raw (mesmo padrão de features_parquet_uri).

    Ex.: s3://bucket/raw/day.csv + 2011-06-01
         → s3://bucket/metrics/2011-06-01/metrics.json
    """
    if not s3_input_path.startswith("s3://"):
        raise ValueError(f"Caminho S3 invalido (esperado s3://...): {s3_input_path}")

    bucket = s3_input_path[5:].split("/", 1)[0]
    return f"s3://{bucket}/metrics/{ref_date}/{METRICS_JSON_NAME}"


def model_pkl_uri(s3_input_path: str, ref_date: str) -> str:
    """
    URI do modelo serializado (S3-02).

    Ex.: s3://bucket/models/2011-06-01/model.pkl
    """
    if not s3_input_path.startswith("s3://"):
        raise ValueError(f"Caminho S3 invalido (esperado s3://...): {s3_input_path}")

    bucket = s3_input_path[5:].split("/", 1)[0]
    return f"s3://{bucket}/models/{ref_date}/{MODEL_PKL_NAME}"


def _parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    """Quebra s3://bucket/key/path em (bucket, key) para boto3."""
    path = s3_uri[5:]
    bucket, key = path.split("/", 1)
    return bucket, key


def s3_object_exists(s3_uri: str) -> bool:
    """True se o objeto existe no S3 (head_object)."""
    if not s3_uri.startswith("s3://"):
        raise ValueError(f"Caminho S3 invalido (esperado s3://...): {s3_uri}")

    bucket, key = _parse_s3_uri(s3_uri)
    try:
        boto3.client("s3").head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def save_model_joblib(model: XGBRegressor, s3_uri: str) -> None:
    """Serializa XGBRegressor com joblib e grava no S3 (S3-02)."""
    import io

    import joblib

    if not s3_uri.startswith("s3://"):
        raise ValueError(f"Caminho S3 invalido (esperado s3://...): {s3_uri}")

    buffer = io.BytesIO()
    joblib.dump(model, buffer)
    buffer.seek(0)

    bucket, key = _parse_s3_uri(s3_uri)
    boto3.client("s3").put_object(
        Bucket=bucket,
        Key=key,
        Body=buffer.getvalue(),
        ContentType="application/octet-stream",
    )
    logger.info("Modelo salvo em %s", s3_uri)


def load_model_joblib(s3_uri: str) -> XGBRegressor:
    """Carrega XGBRegressor de model.pkl no S3 (S3-02)."""
    import io

    import joblib

    if not s3_uri.startswith("s3://"):
        raise ValueError(f"Caminho S3 invalido (esperado s3://...): {s3_uri}")

    bucket, key = _parse_s3_uri(s3_uri)
    response = boto3.client("s3").get_object(Bucket=bucket, Key=key)
    buffer = io.BytesIO(response["Body"].read())
    model = joblib.load(buffer)
    logger.info("Modelo carregado de %s", s3_uri)
    return model


# ---------------------------------------------------------------------------
# Leitura e preparação dos dados
# ---------------------------------------------------------------------------

def read_features_parquet(s3_uri: str) -> pd.DataFrame:
    """Lê features.parquet do S3 (gerado pelo job validate_day_csv)."""
    if not s3_uri.startswith("s3://"):
        raise ValueError(f"Caminho S3 invalido (esperado s3://...): {s3_uri}")

    df = pd.read_parquet(s3_uri, engine="pyarrow")
    logger.info("Features carregadas de %s (shape=%s)", s3_uri, df.shape)
    return df


def split_features_target(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """
    Separa matriz X (features) e vetor y (target=cnt).

    Reutiliza FEATURE_COLUMNS e TARGET_COLUMN de schema_validation
    para manter consistência entre S2 (geração) e S3 (treino).
    """
    missing = [column for column in FEATURE_COLUMNS + (TARGET_COLUMN,) if column not in df.columns]
    if missing:
        if len(missing) == 1:
            raise ValueError(f"Coluna ausente no schema: '{missing[0]}'")
        names = ", ".join(f"'{column}'" for column in missing)
        raise ValueError(f"Colunas ausentes no schema: {names}")

    x = df.loc[:, list(FEATURE_COLUMNS)].copy()
    y = df[TARGET_COLUMN].copy()
    return x, y


def split_train_validation(
    x: pd.DataFrame,
    y: pd.Series,
    *,
    test_size: float = TEST_SIZE,
    random_state: int = RANDOM_STATE,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """
    Split 80/20 reproduzível para treino e validação.

    sklearn train_test_split embaralha com random_state fixo —
    garante mesmas partições entre execuções com os mesmos dados.
    """
    return train_test_split(
        x,
        y,
        test_size=test_size,
        random_state=random_state,
    )


# ---------------------------------------------------------------------------
# Modelo e métricas
# ---------------------------------------------------------------------------

def build_xgboost_regressor(*, random_state: int = RANDOM_STATE) -> XGBRegressor:
    """
    Instancia XGBRegressor com parâmetros básicos para regressão.

    objective=reg:squarederror — minimiza MSE (padrão para RMSE).
    Parâmetros conservadores para dataset pequeno (~30 linhas/mês).
    """
    return XGBRegressor(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        objective="reg:squarederror",
        random_state=random_state,
    )


def compute_regression_metrics(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, float]:
    """
    Calcula RMSE e MAE no conjunto de validação.

    RMSE = sqrt(MSE) — penaliza erros grandes.
    MAE  = média do erro absoluto — mais interpretável em unidades de cnt.
    """
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    return {"rmse": rmse, "mae": mae}


def save_metrics_json(metrics: dict[str, Any], s3_uri: str) -> None:
    """
    Persiste métricas em JSON no S3 via boto3 (disponível nativamente no Glue).

    sort_keys=True — JSON determinístico para diff/versionamento no S3.
    """
    if not s3_uri.startswith("s3://"):
        raise ValueError(f"Caminho S3 invalido (esperado s3://...): {s3_uri}")

    bucket, key = _parse_s3_uri(s3_uri)
    body = json.dumps(metrics, indent=2, sort_keys=True)
    boto3.client("s3").put_object(
        Bucket=bucket,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="application/json",
    )
    logger.info("Metricas salvas em %s", s3_uri)


# ---------------------------------------------------------------------------
# Orquestração principal (chamada pelo Glue Job)
# ---------------------------------------------------------------------------

def train_and_evaluate(
    s3_input_path: str,
    ref_date: str,
    *,
    test_size: float = TEST_SIZE,
    random_state: int = RANDOM_STATE,
    force_retrain: bool = False,
) -> dict[str, Any]:
    """
    Pipeline S3-01 + S3-02: leitura → split → treino ou reuse → avaliação → model.pkl + JSON.

    Se model.pkl existir e force_retrain=False, carrega o modelo e pula fit (reavalia RMSE/MAE).
    """
    features_uri = features_parquet_uri(s3_input_path, ref_date)
    df = read_features_parquet(features_uri)
    x, y = split_features_target(df)

    if len(x) < 2:
        raise ValueError(
            f"Insuficientes registros para treino (n={len(x)}); minimo 2 necessarios."
        )

    x_train, x_val, y_train, y_val = split_train_validation(
        x,
        y,
        test_size=test_size,
        random_state=random_state,
    )

    model_uri = model_pkl_uri(s3_input_path, ref_date)
    model_reused = False

    if not force_retrain and s3_object_exists(model_uri):
        model = load_model_joblib(model_uri)
        model_reused = True
        logger.info("Modelo reutilizado de %s (treino ignorado)", model_uri)
    else:
        model = build_xgboost_regressor(random_state=random_state)
        model.fit(x_train, y_train)
        save_model_joblib(model, model_uri)
        logger.info("Modelo treinado e salvo em %s", model_uri)

    y_pred = model.predict(x_val)
    scores = compute_regression_metrics(y_val, y_pred)

    logger.info("RMSE=%.4f MAE=%.4f", scores["rmse"], scores["mae"])

    metrics: dict[str, Any] = {
        "ref_date": ref_date,
        "features_parquet": features_uri,
        "random_state": random_state,
        "test_size": test_size,
        "n_samples": len(x),
        "n_train": len(x_train),
        "n_val": len(x_val),
        "model_pkl": model_uri,
        "model_reused": model_reused,
        **scores,
    }

    metrics_uri = metrics_json_uri(s3_input_path, ref_date)
    save_metrics_json(metrics, metrics_uri)
    metrics["metrics_json"] = metrics_uri

    return metrics


def train_and_evaluate_with_observability(
    s3_input_path: str,
    ref_date: str,
    *,
    test_size: float = TEST_SIZE,
    random_state: int = RANDOM_STATE,
    rmse_threshold: float | None = None,
    cloudwatch_namespace: str | None = None,
    force_retrain: bool = False,
) -> dict[str, Any]:
    """
    S3-01 + S4-03: treino, metricas S3 e publicacao RMSE/MAE no CloudWatch.
    """
    from pipeline_observability import DEFAULT_NAMESPACE, publish_training_metrics

    metrics = train_and_evaluate(
        s3_input_path,
        ref_date,
        test_size=test_size,
        random_state=random_state,
        force_retrain=force_retrain,
    )

    namespace = cloudwatch_namespace or DEFAULT_NAMESPACE
    breached = publish_training_metrics(
        namespace=namespace,
        ref_date=ref_date,
        rmse=metrics["rmse"],
        mae=metrics["mae"],
        rmse_threshold=rmse_threshold,
    )

    metrics["rmse_threshold"] = rmse_threshold
    metrics["rmse_threshold_breached"] = breached
    metrics["cloudwatch_namespace"] = namespace
    return metrics
