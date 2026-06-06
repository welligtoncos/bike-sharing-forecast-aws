"""
Utilitário dev — gera predictions.parquet de amostra até existir job de inferência.

Monta dteday + cnt_real (day.csv) e cnt_pred (XGBoost treinado in-memory nas features).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from glue_catalog_predictions import predictions_parquet_uri
from schema_validation import (
    TARGET_COLUMN,
    DATE_COLUMN,
    features_parquet_uri,
    process_day_csv,
)
from xgboost_training import (
    build_xgboost_regressor,
    read_features_parquet,
    split_features_target,
)

logger = logging.getLogger(__name__)


def generate_sample_predictions_parquet(s3_input_path: str, ref_date: str) -> str:
    """
    Gera s3://{bucket}/predictions/ref_date={ref_date}/predictions.parquet.

    Pré-requisitos:
      - raw/day.csv no S3
      - features/{ref_date}/features.parquet (job validate_day_csv)

    Returns:
        URI S3 do Parquet gravado.
    """
    filtered = process_day_csv(s3_input_path, ref_date)
    if filtered is None or filtered.empty:
        raise ValueError(
            f"Nenhum registro em day.csv para ref_date={ref_date}; "
            "nao e possivel gerar predictions.parquet."
        )

    features_uri = features_parquet_uri(s3_input_path, ref_date)
    features_df = read_features_parquet(features_uri)
    x, y = split_features_target(features_df)

    if len(filtered) != len(features_df):
        raise ValueError(
            f"Contagem divergente: day.csv filtrado={len(filtered)}, "
            f"features={len(features_df)}. Regere features para {ref_date}."
        )

    model = build_xgboost_regressor()
    model.fit(x, y)
    cnt_pred = model.predict(x)

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
        "Sample predictions salvas em %s (shape=%s)",
        output_uri,
        output.shape,
    )
    return output_uri
