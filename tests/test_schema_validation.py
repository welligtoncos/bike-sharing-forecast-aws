"""Testes S2-01 — validacao de schema day.csv."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from schema_validation import (  # noqa: E402
    REQUIRED_COLUMNS,
    load_and_validate_day_csv,
    read_day_csv_from_s3,
    validate_schema,
)


def _valid_day_frame(rows: int = 5) -> pd.DataFrame:
    return pd.DataFrame({column: list(range(rows)) for column in REQUIRED_COLUMNS})


def test_validate_schema_accepts_all_required_columns() -> None:
    validate_schema(_valid_day_frame())


def test_validate_schema_raises_value_error_for_missing_column() -> None:
    df = _valid_day_frame().drop(columns=["hum"])

    with pytest.raises(ValueError, match="Coluna ausente no schema: 'hum'"):
        validate_schema(df)


def test_validate_schema_lists_multiple_missing_columns() -> None:
    df = _valid_day_frame().drop(columns=["hum", "cnt"])

    with pytest.raises(ValueError, match="'hum'") as exc_info:
        validate_schema(df)

    assert "'cnt'" in str(exc_info.value)


def test_read_day_csv_from_s3_rejects_non_s3_path() -> None:
    with pytest.raises(ValueError, match="Caminho S3 invalido"):
        read_day_csv_from_s3("/local/day.csv")


@patch("schema_validation.pd.read_csv")
def test_load_and_validate_day_csv_reads_via_s3fs(mock_read_csv) -> None:
    expected = _valid_day_frame(3)
    mock_read_csv.return_value = expected

    result = load_and_validate_day_csv("s3://bucket/raw/day.csv")

    mock_read_csv.assert_called_once_with("s3://bucket/raw/day.csv")
    assert result.shape == (3, len(REQUIRED_COLUMNS))


@patch("schema_validation.pd.read_csv")
def test_load_and_validate_day_csv_logs_shape(mock_read_csv, caplog) -> None:
    mock_read_csv.return_value = _valid_day_frame(10)

    with caplog.at_level("INFO"):
        load_and_validate_day_csv("s3://bucket/raw/day.csv")

    assert "DataFrame shape: (10, 6)" in caplog.text


@patch("schema_validation.pd.read_csv")
def test_load_and_validate_day_csv_propagates_schema_error(mock_read_csv) -> None:
    mock_read_csv.return_value = _valid_day_frame().drop(columns=["weekday"])

    with pytest.raises(ValueError, match="'weekday'"):
        load_and_validate_day_csv("s3://bucket/raw/day.csv")
