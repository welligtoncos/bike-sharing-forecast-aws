"""
Testes S2-01 / S2-02 / S2-03 — validação, filtro e Parquet day.csv.

Estratégia de testes
--------------------
  - Unitários puros (sem AWS): mocks de pd.read_csv e to_parquet.
  - _valid_day_frame(): factory de DataFrame sintético com schema Bike Sharing.
  - caplog: verifica mensagens INFO/WARNING exigidas pelos critérios de aceite.

Como executar
-------------
  python -m pytest tests/test_schema_validation.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

# Permite importar scripts/ sem instalar pacote (mesmo layout do Glue extra-py-files).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from schema_validation import (  # noqa: E402
    DATE_COLUMN,
    FEATURE_COLUMNS,
    OUTPUT_COLUMNS,
    REQUIRED_COLUMNS,
    TARGET_COLUMN,
    features_parquet_uri,
    filter_by_ref_date,
    load_and_validate_day_csv,
    process_and_save_features,
    process_day_csv,
    read_day_csv_from_s3,
    select_feature_columns,
    save_features_parquet,
    validate_schema,
)


def _valid_day_frame(rows: int = 5, start: str = "2024-06-01") -> pd.DataFrame:
    """Cria DataFrame mínimo válido para testes (todas as REQUIRED_COLUMNS)."""
    data = {column: list(range(rows)) for column in REQUIRED_COLUMNS if column != DATE_COLUMN}
    data[DATE_COLUMN] = pd.date_range(start, periods=rows, freq="D").strftime("%Y-%m-%d")
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# S2-01 — validate_schema
# ---------------------------------------------------------------------------

def test_validate_schema_accepts_all_required_columns() -> None:
    """Schema completo não deve levantar exceção."""
    validate_schema(_valid_day_frame())


def test_validate_schema_raises_value_error_for_missing_column() -> None:
    """Uma coluna faltante → ValueError com nome explícito."""
    df = _valid_day_frame().drop(columns=["hum"])

    with pytest.raises(ValueError, match="Coluna ausente no schema: 'hum'"):
        validate_schema(df)


def test_validate_schema_lists_multiple_missing_columns() -> None:
    """Várias colunas faltantes → mensagem lista todas."""
    df = _valid_day_frame().drop(columns=["hum", "cnt"])

    with pytest.raises(ValueError, match="'hum'") as exc_info:
        validate_schema(df)

    assert "'cnt'" in str(exc_info.value)


# ---------------------------------------------------------------------------
# S2-01 — leitura S3 (mockada)
# ---------------------------------------------------------------------------

def test_read_day_csv_from_s3_rejects_non_s3_path() -> None:
    """Paths locais devem ser rejeitados antes de chamar pandas."""
    with pytest.raises(ValueError, match="Caminho S3 invalido"):
        read_day_csv_from_s3("/local/day.csv")


@patch("schema_validation.pd.read_csv")
def test_load_and_validate_day_csv_reads_via_s3fs(mock_read_csv) -> None:
    """read_csv recebe URI s3:// diretamente (s3fs transparente)."""
    expected = _valid_day_frame(3)
    mock_read_csv.return_value = expected

    result = load_and_validate_day_csv("s3://bucket/raw/day.csv")

    mock_read_csv.assert_called_once_with("s3://bucket/raw/day.csv")
    assert result.shape == (3, len(REQUIRED_COLUMNS))


@patch("schema_validation.pd.read_csv")
def test_load_and_validate_day_csv_logs_shape(mock_read_csv, caplog) -> None:
    """Critério S2-01: shape logado após leitura."""
    mock_read_csv.return_value = _valid_day_frame(10)

    with caplog.at_level("INFO"):
        load_and_validate_day_csv("s3://bucket/raw/day.csv")

    assert "DataFrame shape: (10, 7)" in caplog.text


@patch("schema_validation.pd.read_csv")
def test_load_and_validate_day_csv_propagates_schema_error(mock_read_csv) -> None:
    """Erro de schema após leitura deve propagar (não engolir)."""
    mock_read_csv.return_value = _valid_day_frame().drop(columns=["weekday"])

    with pytest.raises(ValueError, match="'weekday'"):
        load_and_validate_day_csv("s3://bucket/raw/day.csv")


# ---------------------------------------------------------------------------
# S2-02 — filter_by_ref_date
# ---------------------------------------------------------------------------

def test_filter_by_ref_date_keeps_matching_month_and_year() -> None:
    """Filtra por mês/ano, não pelo dia exato de ref_date."""
    df = pd.DataFrame(
        {
            DATE_COLUMN: ["2024-06-01", "2024-06-15", "2024-07-01", "2023-06-10"],
            "cnt": [10, 20, 30, 40],
        }
    )

    result = filter_by_ref_date(df, "2024-06-01")

    assert len(result) == 2
    assert list(result[DATE_COLUMN]) == ["2024-06-01", "2024-06-15"]


def test_filter_by_ref_date_logs_filtered_count(caplog) -> None:
    """Critério S2-02: quantidade filtrada aparece no log."""
    df = _valid_day_frame(3, start="2024-06-01")

    with caplog.at_level("INFO"):
        filter_by_ref_date(df, "2024-06-01")

    assert "Quantidade de registros filtrados para 2024-06: 3" in caplog.text


def test_filter_by_ref_date_empty_when_month_has_no_data() -> None:
    """Mês sem overlap → DataFrame vazio (não exceção)."""
    df = _valid_day_frame(3, start="2024-07-01")

    result = filter_by_ref_date(df, "2024-06-01")

    assert result.empty


@patch("schema_validation.pd.read_csv")
def test_process_day_csv_empty_month_logs_warning_and_returns_none(mock_read_csv, caplog) -> None:
    """Critério S2-02: mês vazio → warning + None (job SUCCEEDED)."""
    mock_read_csv.return_value = _valid_day_frame(3, start="2024-07-01")

    with caplog.at_level("WARNING"):
        result = process_day_csv("s3://bucket/raw/day.csv", "2024-06-01")

    assert result is None
    assert "Nenhum registro encontrado para ref_date=2024-06-01" in caplog.text


@patch("schema_validation.pd.read_csv")
def test_process_day_csv_does_not_raise_on_empty_month(mock_read_csv) -> None:
    """Garante que empty month nunca levanta exceção."""
    mock_read_csv.return_value = _valid_day_frame(2, start="2024-08-01")

    result = process_day_csv("s3://bucket/raw/day.csv", "2024-06-01")

    assert result is None


@patch("schema_validation.pd.read_csv")
def test_process_day_csv_returns_filtered_dataframe(mock_read_csv) -> None:
    """Mês com dados → DataFrame não nulo."""
    mock_read_csv.return_value = _valid_day_frame(5, start="2024-06-01")

    result = process_day_csv("s3://bucket/raw/day.csv", "2024-06-01")

    assert result is not None
    assert len(result) == 5


# ---------------------------------------------------------------------------
# S2-03 — Parquet e orquestração
# ---------------------------------------------------------------------------

def test_features_parquet_uri_from_raw_path() -> None:
    """URI de saída segue convenção features/{ref_date}/features.parquet."""
    uri = features_parquet_uri(
        "s3://glue-b3-dev-s3-pipeline-303238378103/raw/day.csv",
        "2011-06-01",
    )

    assert uri == "s3://glue-b3-dev-s3-pipeline-303238378103/features/2011-06-01/features.parquet"


def test_select_feature_columns_keeps_features_and_target() -> None:
    """Colunas extras do CSV original são descartadas."""
    df = _valid_day_frame(4)
    extra = df.assign(instant=1, casual=2, registered=3)

    result = select_feature_columns(extra)

    assert list(result.columns) == list(OUTPUT_COLUMNS)
    assert list(result.columns) == list(FEATURE_COLUMNS) + [TARGET_COLUMN]


def test_save_features_parquet_roundtrip_local(tmp_path) -> None:
    """Roundtrip Parquet local (pyarrow) preserva schema e linhas."""
    pytest.importorskip("pyarrow")
    df = select_feature_columns(_valid_day_frame(3))
    parquet_path = tmp_path / "features.parquet"

    df.to_parquet(parquet_path, engine="pyarrow", index=False)
    loaded = pd.read_parquet(parquet_path)

    assert list(loaded.columns) == list(OUTPUT_COLUMNS)
    assert len(loaded) == 3


@patch("schema_validation.save_features_parquet")
@patch("schema_validation.process_day_csv")
def test_process_and_save_features_writes_partitioned_path(mock_process, mock_save) -> None:
    """Orquestrador grava no path particionado correto."""
    mock_process.return_value = _valid_day_frame(2, start="2011-06-01")

    uri = process_and_save_features(
        "s3://my-bucket/raw/day.csv",
        "2011-06-01",
    )

    assert uri == "s3://my-bucket/features/2011-06-01/features.parquet"
    mock_save.assert_called_once()
    saved_df = mock_save.call_args[0][0]
    assert list(saved_df.columns) == list(OUTPUT_COLUMNS)


@patch("schema_validation.process_day_csv")
def test_process_and_save_features_skips_empty_month(mock_process) -> None:
    """Mês vazio → retorna None sem chamar save."""
    mock_process.return_value = None

    assert process_and_save_features("s3://my-bucket/raw/day.csv", "1999-01-01") is None


@patch("schema_validation.pd.DataFrame.to_parquet")
def test_save_features_parquet_uses_pyarrow(mock_to_parquet) -> None:
    """Escrita S3 usa engine pyarrow (critério S2-03)."""
    df = select_feature_columns(_valid_day_frame(1))

    save_features_parquet(df, "s3://my-bucket/features/2011-06-01/features.parquet")

    mock_to_parquet.assert_called_once_with(
        "s3://my-bucket/features/2011-06-01/features.parquet",
        engine="pyarrow",
        index=False,
    )
