"""
S2-01 / S2-02 — Leitura, validacao de schema e filtro por ref_date (day.csv).

Le o CSV do S3 via pandas + s3fs, valida colunas obrigatorias e filtra
registros cujo dteday corresponde ao mes/ano de ref_date.
"""

from __future__ import annotations

import logging
from typing import Sequence

import pandas as pd

logger = logging.getLogger(__name__)

DATE_COLUMN = "dteday"

REQUIRED_COLUMNS: tuple[str, ...] = (
    "season",
    "temp",
    "hum",
    "windspeed",
    "weekday",
    "cnt",
    DATE_COLUMN,
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


def parse_ref_date(ref_date: str) -> tuple[int, int]:
    """Extrai ano e mes de ref_date (formato YYYY-MM-DD)."""
    parsed = pd.to_datetime(ref_date)
    return int(parsed.year), int(parsed.month)


def filter_by_ref_date(
    df: pd.DataFrame,
    ref_date: str,
    date_column: str = DATE_COLUMN,
) -> pd.DataFrame:
    """Mantem apenas registros cujo dteday pertence ao mes/ano de ref_date."""
    if date_column not in df.columns:
        raise ValueError(f"Coluna ausente no schema: '{date_column}'")

    year, month = parse_ref_date(ref_date)
    dates = pd.to_datetime(df[date_column])
    mask = (dates.dt.year == year) & (dates.dt.month == month)
    filtered = df.loc[mask].copy()

    logger.info(
        "Quantidade de registros filtrados para %04d-%02d: %d",
        year,
        month,
        len(filtered),
    )
    return filtered


def process_day_csv(s3_path: str, ref_date: str) -> pd.DataFrame | None:
    """
    Carrega, valida e filtra day.csv.

    Retorna None se nao houver registros no mes (warning logado, sem erro fatal).
    """
    df = load_and_validate_day_csv(s3_path)
    filtered = filter_by_ref_date(df, ref_date)

    if filtered.empty:
        logger.warning(
            "Nenhum registro encontrado para ref_date=%s; encerrando job sem erro.",
            ref_date,
        )
        return None

    logger.info("DataFrame shape apos filtro: %s", filtered.shape)
    return filtered
