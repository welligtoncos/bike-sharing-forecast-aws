"""
S2-01 / S2-02 / S2-03 — Leitura, validação, filtro e persistência Parquet (day.csv).

Propósito
---------
Módulo compartilhado entre o Glue Job validate_day_csv e os testes unitários.
Implementa o pipeline de features a partir do CSV bruto Bike Sharing:

  1. S2-01 — Validar schema (colunas obrigatórias)
  2. S2-02 — Filtrar registros pelo mês/ano de ref_date (coluna dteday)
  3. S2-03 — Selecionar features + target e salvar Parquet no S3

Dependências Glue
-----------------
  pandas, s3fs (leitura CSV S3), pyarrow (escrita Parquet S3).

Contrato de saída
-----------------
  s3://{bucket}/features/{ref_date}/features.parquet
  Colunas: season, temp, hum, windspeed, weekday, cnt
"""

from __future__ import annotations

import logging
from typing import Sequence

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes de schema — alinhadas ao dataset Bike Sharing (day.csv)
# ---------------------------------------------------------------------------

# Coluna de data usada para filtrar o mês de referência.
DATE_COLUMN = "dteday"

# Variável alvo (contagem de bikes alugadas) — usada no treino S3-01.
TARGET_COLUMN = "cnt"

# Features numéricas/categóricas selecionadas para o modelo.
FEATURE_COLUMNS: tuple[str, ...] = (
    "season",
    "temp",
    "hum",
    "windspeed",
    "weekday",
)

# Colunas exigidas na leitura do CSV bruto (features + target + data).
REQUIRED_COLUMNS: tuple[str, ...] = FEATURE_COLUMNS + (TARGET_COLUMN, DATE_COLUMN)

# Colunas persistidas no Parquet (sem dteday — já filtrado por ref_date).
OUTPUT_COLUMNS: tuple[str, ...] = FEATURE_COLUMNS + (TARGET_COLUMN,)

# Nome fixo do arquivo de saída dentro da pasta features/{ref_date}/.
FEATURES_PARQUET_NAME = "features.parquet"


# ---------------------------------------------------------------------------
# S2-01 — Validação de schema
# ---------------------------------------------------------------------------

def validate_schema(df: pd.DataFrame, required: Sequence[str] = REQUIRED_COLUMNS) -> None:
    """
    Garante que todas as colunas obrigatórias existem no DataFrame.

    Levanta ValueError com mensagem clara (nome da coluna faltante) para
    falha rápida antes de processar dados inválidos.

    Raises:
        ValueError: se uma ou mais colunas estiverem ausentes.
    """
    missing = [column for column in required if column not in df.columns]
    if not missing:
        return

    # Mensagem singular vs plural — facilita debug no CloudWatch.
    if len(missing) == 1:
        raise ValueError(f"Coluna ausente no schema: '{missing[0]}'")

    names = ", ".join(f"'{column}'" for column in missing)
    raise ValueError(f"Colunas ausentes no schema: {names}")


def read_day_csv_from_s3(s3_path: str) -> pd.DataFrame:
    """
    Lê day.csv do S3 via pd.read_csv.

    O s3fs (instalado como additional-python-modules no Glue) permite
    que pandas leia URIs s3:// diretamente, sem boto3 manual.

    Raises:
        ValueError: se o path não começar com s3://.
    """
    if not s3_path.startswith("s3://"):
        raise ValueError(f"Caminho S3 invalido (esperado s3://...): {s3_path}")

    return pd.read_csv(s3_path)


def load_and_validate_day_csv(s3_path: str) -> pd.DataFrame:
    """Orquestra leitura S3 + validação de schema + log de shape."""
    df = read_day_csv_from_s3(s3_path)
    validate_schema(df)
    logger.info("DataFrame shape: %s", df.shape)
    return df


# ---------------------------------------------------------------------------
# S2-02 — Filtro por ref_date (mês/ano de dteday)
# ---------------------------------------------------------------------------

def parse_ref_date(ref_date: str) -> tuple[int, int]:
    """
    Extrai (ano, mês) de ref_date no formato YYYY-MM-DD.

    Ex.: "2011-06-01" → (2011, 6)
    O dia é ignorado — apenas mês/ano definem a partição mensal.
    """
    parsed = pd.to_datetime(ref_date)
    return int(parsed.year), int(parsed.month)


def filter_by_ref_date(
    df: pd.DataFrame,
    ref_date: str,
    date_column: str = DATE_COLUMN,
) -> pd.DataFrame:
    """
    Mantém apenas registros cujo dteday pertence ao mês/ano de ref_date.

    Critério de aceite S2-02: filtrar por mês e ano, não pelo dia exato.
    """
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
    Pipeline S2-01 + S2-02: carrega, valida e filtra day.csv.

    Retorna None (não levanta exceção) se o mês não tiver registros —
    comportamento esperado para ref_dates futuros ou meses vazios no dataset.

    Returns:
        DataFrame filtrado ou None se filtered.empty.
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


# ---------------------------------------------------------------------------
# S2-03 — Seleção de colunas e persistência Parquet
# ---------------------------------------------------------------------------

def select_feature_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Reduz o DataFrame às colunas de modelagem (features + cnt).

    Descarta colunas extras do CSV original (instant, casual, registered, etc.).
    """
    missing = [column for column in OUTPUT_COLUMNS if column not in df.columns]
    if missing:
        if len(missing) == 1:
            raise ValueError(f"Coluna ausente no schema: '{missing[0]}'")
        names = ", ".join(f"'{column}'" for column in missing)
        raise ValueError(f"Colunas ausentes no schema: {names}")

    return df.loc[:, list(OUTPUT_COLUMNS)].copy()


def features_parquet_uri(s3_input_path: str, ref_date: str) -> str:
    """
    Deriva o URI de saída a partir do path raw — evita passar bucket separado.

    Entrada: s3://my-bucket/raw/day.csv + ref_date=2011-06-01
    Saída:   s3://my-bucket/features/2011-06-01/features.parquet
    """
    if not s3_input_path.startswith("s3://"):
        raise ValueError(f"Caminho S3 invalido (esperado s3://...): {s3_input_path}")

    # Remove "s3://" e pega o primeiro segmento como nome do bucket.
    bucket = s3_input_path[5:].split("/", 1)[0]
    return f"s3://{bucket}/features/{ref_date}/{FEATURES_PARQUET_NAME}"


def save_features_parquet(df: pd.DataFrame, s3_uri: str) -> None:
    """
    Persiste DataFrame em Parquet no S3 (pandas + engine pyarrow).

    index=False — dteday não faz parte do OUTPUT_COLUMNS; índice não é necessário.
    """
    if not s3_uri.startswith("s3://"):
        raise ValueError(f"Caminho S3 invalido (esperado s3://...): {s3_uri}")

    df.to_parquet(s3_uri, engine="pyarrow", index=False)
    logger.info("Features salvas em %s (shape=%s, colunas=%s)", s3_uri, df.shape, list(df.columns))


def process_and_save_features(s3_path: str, ref_date: str) -> str | None:
    """
    Orquestra o pipeline completo S2-01 → S2-02 → S2-03.

    Chamado pelo Glue Job validate_day_csv_job.py.

    Returns:
        URI do Parquet gravado, ou None se o mês estiver vazio.
    """
    filtered = process_day_csv(s3_path, ref_date)
    if filtered is None:
        return None

    features = select_feature_columns(filtered)
    output_uri = features_parquet_uri(s3_path, ref_date)
    save_features_parquet(features, output_uri)
    return output_uri
