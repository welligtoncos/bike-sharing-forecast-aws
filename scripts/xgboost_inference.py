"""
S3-03 — Inferência XGBoost: predições mensais a partir de model.pkl.

Gera predictions.parquet com dteday, cnt_real, cnt_pred para registro no Glue Catalog.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from glue_catalog_predictions import predictions_parquet_uri
from schema_validation import DATE_COLUMN, TARGET_COLUMN, features_parquet_uri, process_day_csv
from xgboost_training import (
    load_model_joblib,
    model_pkl_uri,
    read_features_parquet,
    s3_object_exists,
    split_features_target,
)

logger = logging.getLogger(__name__)


def generate_predictions_parquet(s3_input_path: str, ref_date: str) -> str:
    """
    Gera s3://{bucket}/predictions/ref_date={ref_date}/predictions.parquet.

    Pré-requisitos:
      - features/{ref_date}/features.parquet (S2)
      - models/{ref_date}/model.pkl (S3-02)

    Returns:
        URI S3 do Parquet gravado.
    """
    model_uri = model_pkl_uri(s3_input_path, ref_date)
    if not s3_object_exists(model_uri):
        raise ValueError(
            f"Modelo nao encontrado em {model_uri}. "
            "Execute o job train-xgboost antes da inferencia."
        )

    filtered = process_day_csv(s3_input_path, ref_date)
    if filtered is None or filtered.empty:
        raise ValueError(
            f"Nenhum registro em day.csv para ref_date={ref_date}; "
            "nao e possivel gerar predictions.parquet."
        )

    features_uri = features_parquet_uri(s3_input_path, ref_date)
    features_df = read_features_parquet(features_uri)
    x, _y = split_features_target(features_df)

    if len(filtered) != len(features_df):
        raise ValueError(
            f"Contagem divergente: day.csv filtrado={len(filtered)}, "
            f"features={len(features_df)}. Regere features para {ref_date}."
        )

    model = load_model_joblib(model_uri)
    cnt_pred = np.maximum(model.predict(x), 0.0)

    output = pd.DataFrame(
        {
            "dteday": pd.to_datetime(filtered[DATE_COLUMN]).dt.strftime("%Y-%m-%d"),
            "cnt_real": filtered[TARGET_COLUMN].astype("int64"),
            "cnt_pred": np.asarray(cnt_pred, dtype=float),
        }
    )

    output_uri = predictions_parquet_uri(s3_input_path, ref_date)
    output.to_parquet(output_uri, engine="pyarrow", index=False)
    logger.info(
        "Predicoes salvas em %s (shape=%s, model=%s)",
        output_uri,
        output.shape,
        model_uri,
    )
    return output_uri
