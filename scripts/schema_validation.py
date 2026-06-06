"""
S2-01 — Validacao de schema do day.csv (Bike Sharing).

Le o CSV do S3 via pandas + s3fs e garante que as colunas obrigatorias
existem antes do feature engineering / treino do modelo.
"""

from __future__ import annotations

import logging
from typing import Sequence

import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS: tuple[str, ...] = (
    "season",
    "temp",
    "hum",
    "windspeed",
    "weekday",
    "cnt",
)


def validate_schema(df: pd.DataFrame, required: Sequence[str] = REQUIRED_COLUMNS) -> None:
    """Valida colunas obrigatorias. Levanta ValueError com o nome da coluna faltante."""
    missing = [column for column in required if column not in df.columns]
    if not missing:
        return

    if len(missing) == 1:
        raise ValueError(f"Coluna ausente no schema: '{missing[0]}'")

    names = ", ".join(f"'{column}'" for column in missing)
    raise ValueError(f"Colunas ausentes no schema: {names}")


def read_day_csv_from_s3(s3_path: str) -> pd.DataFrame:
    """Le day.csv do S3 usando pd.read_csv (requer s3fs instalado)."""
    if not s3_path.startswith("s3://"):
        raise ValueError(f"Caminho S3 invalido (esperado s3://...): {s3_path}")

    return pd.read_csv(s3_path)


def load_and_validate_day_csv(s3_path: str) -> pd.DataFrame:
    """Le day.csv do S3, valida schema e registra shape no log."""
    df = read_day_csv_from_s3(s3_path)
    validate_schema(df)
    logger.info("DataFrame shape: %s", df.shape)
    return df
