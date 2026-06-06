"""Testes S2-01 / S2-02 — validacao de schema e filtro day.csv."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from schema_validation import (  # noqa: E402
    DATE_COLUMN,
    REQUIRED_COLUMNS,
    filter_by_ref_date,
    load_and_validate_day_csv,
    process_day_csv,
    read_day_csv_from_s3,
    validate_schema,
)


def _valid_day_frame(rows: int = 5, start: str = "2024-06-01") -> pd.DataFrame:
    data = {column: list(range(rows)) for column in REQUIRED_COLUMNS if column != DATE_COLUMN}
    data[DATE_COLUMN] = pd.date_range(start, periods=rows, freq="D").strftime("%Y-%m-%d")
    return pd.DataFrame(data)


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

    assert "DataFrame shape: (10, 7)" in caplog.text


@patch("schema_validation.pd.read_csv")
def test_load_and_validate_day_csv_propagates_schema_error(mock_read_csv) -> None:
    mock_read_csv.return_value = _valid_day_frame().drop(columns=["weekday"])

    with pytest.raises(ValueError, match="'weekday'"):
        load_and_validate_day_csv("s3://bucket/raw/day.csv")


def test_filter_by_ref_date_keeps_matching_month_and_year() -> None:
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
    df = _valid_day_frame(3, start="2024-06-01")

    with caplog.at_level("INFO"):
        filter_by_ref_date(df, "2024-06-01")

    assert "Quantidade de registros filtrados para 2024-06: 3" in caplog.text


def test_filter_by_ref_date_empty_when_month_has_no_data() -> None:
    df = _valid_day_frame(3, start="2024-07-01")

    result = filter_by_ref_date(df, "2024-06-01")

    assert result.empty


@patch("schema_validation.pd.read_csv")
def test_process_day_csv_empty_month_logs_warning_and_returns_none(mock_read_csv, caplog) -> None:
    mock_read_csv.return_value = _valid_day_frame(3, start="2024-07-01")

    with caplog.at_level("WARNING"):
        result = process_day_csv("s3://bucket/raw/day.csv", "2024-06-01")

    assert result is None
    assert "Nenhum registro encontrado para ref_date=2024-06-01" in caplog.text


@patch("schema_validation.pd.read_csv")
def test_process_day_csv_does_not_raise_on_empty_month(mock_read_csv) -> None:
    mock_read_csv.return_value = _valid_day_frame(2, start="2024-08-01")

    result = process_day_csv("s3://bucket/raw/day.csv", "2024-06-01")

    assert result is None


@patch("schema_validation.pd.read_csv")
def test_process_day_csv_returns_filtered_dataframe(mock_read_csv) -> None:
    mock_read_csv.return_value = _valid_day_frame(5, start="2024-06-01")

    result = process_day_csv("s3://bucket/raw/day.csv", "2024-06-01")

    assert result is not None
    assert len(result) == 5
