"""Testes S4-01 — Glue Catalog predictions (boto3)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from glue_catalog_predictions import (  # noqa: E402
    DATABASE_NAME_DEFAULT,
    PARTITION_KEY,
    REQUIRED_COLUMNS,
    TABLE_NAME,
    create_or_update_table,
    ensure_database,
    infer_glue_columns_from_parquet,
    pandas_dtype_to_glue,
    predictions_parquet_uri,
    predictions_partition_location,
    predictions_table_root_uri,
    register_partition,
    register_predictions_table,
)


def _predictions_frame(rows: int = 5) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "dteday": pd.date_range("2011-06-01", periods=rows, freq="D").strftime("%Y-%m-%d"),
            "cnt_real": list(range(100, 100 + rows)),
            "cnt_pred": [float(100 + index) for index in range(rows)],
        }
    )


def test_predictions_uris_hive_partition_layout() -> None:
    raw = "s3://my-bucket/raw/day.csv"
    ref = "2011-06-01"

    assert predictions_table_root_uri(raw) == "s3://my-bucket/predictions/"
    assert (
        predictions_parquet_uri(raw, ref)
        == "s3://my-bucket/predictions/ref_date=2011-06-01/predictions.parquet"
    )
    assert (
        predictions_partition_location(raw, ref)
        == "s3://my-bucket/predictions/ref_date=2011-06-01/"
    )


def test_pandas_dtype_to_glue_mapping() -> None:
    df = _predictions_frame(1)
    assert pandas_dtype_to_glue(df["cnt_real"].dtype) == "bigint"
    assert pandas_dtype_to_glue(df["cnt_pred"].dtype) == "double"
    assert pandas_dtype_to_glue(df["dteday"].dtype) == "string"


@patch("glue_catalog_predictions.pd.read_parquet")
def test_infer_glue_columns_from_parquet(mock_read_parquet) -> None:
    mock_read_parquet.return_value = _predictions_frame(3)

    columns = infer_glue_columns_from_parquet(
        "s3://my-bucket/predictions/ref_date=2011-06-01/predictions.parquet"
    )

    assert [column["Name"] for column in columns] == list(REQUIRED_COLUMNS)
    assert columns[0]["Name"] == "dteday"
    assert columns[1]["Name"] == "cnt_real"
    assert columns[2]["Name"] == "cnt_pred"


@patch("glue_catalog_predictions.pd.read_parquet")
def test_infer_glue_columns_raises_on_missing_column(mock_read_parquet) -> None:
    mock_read_parquet.return_value = _predictions_frame(2).drop(columns=["cnt_pred"])

    with pytest.raises(ValueError, match="cnt_pred"):
        infer_glue_columns_from_parquet(
            "s3://my-bucket/predictions/ref_date=2011-06-01/predictions.parquet"
        )


def _mock_glue_client() -> MagicMock:
    client = MagicMock()
    client.exceptions.EntityNotFoundException = type("EntityNotFoundException", (Exception,), {})
    return client


def test_ensure_database_creates_when_missing() -> None:
    glue = _mock_glue_client()
    glue.get_database.side_effect = glue.exceptions.EntityNotFoundException()

    ensure_database(glue, DATABASE_NAME_DEFAULT, location_uri="s3://b/predictions/")

    glue.create_database.assert_called_once()
    assert glue.create_database.call_args.kwargs["DatabaseInput"]["Name"] == "bike_sharing"


def test_ensure_database_skips_when_exists() -> None:
    glue = _mock_glue_client()
    glue.get_database.return_value = {"Database": {"Name": "bike_sharing"}}

    ensure_database(glue, DATABASE_NAME_DEFAULT)

    glue.create_database.assert_not_called()


def test_create_or_update_table_creates_new_table() -> None:
    glue = _mock_glue_client()
    glue.get_table.side_effect = glue.exceptions.EntityNotFoundException()
    columns = [{"Name": "dteday", "Type": "string"}]

    create_or_update_table(glue, "bike_sharing", columns, "s3://b/predictions/")

    glue.create_table.assert_called_once()
    table_input = glue.create_table.call_args.kwargs["TableInput"]
    assert table_input["Name"] == TABLE_NAME
    assert table_input["PartitionKeys"] == [{"Name": PARTITION_KEY, "Type": "string"}]


def test_create_or_update_table_updates_existing() -> None:
    glue = _mock_glue_client()
    glue.get_table.return_value = {"Table": {"Name": TABLE_NAME}}
    columns = [{"Name": "dteday", "Type": "string"}]

    create_or_update_table(glue, "bike_sharing", columns, "s3://b/predictions/")

    glue.update_table.assert_called_once()


def test_register_partition_creates_partition() -> None:
    glue = MagicMock()
    columns = [{"Name": "dteday", "Type": "string"}]

    register_partition(
        glue,
        "bike_sharing",
        "2011-06-01",
        columns,
        "s3://b/predictions/ref_date=2011-06-01/",
    )

    glue.create_partition.assert_called_once()
    partition = glue.create_partition.call_args.kwargs["PartitionInput"]
    assert partition["Values"] == ["2011-06-01"]


def test_register_partition_updates_on_conflict() -> None:
    glue = MagicMock()
    glue.create_partition.side_effect = ClientError(
        {"Error": {"Code": "AlreadyExistsException", "Message": "exists"}},
        "CreatePartition",
    )
    columns = [{"Name": "dteday", "Type": "string"}]

    register_partition(
        glue,
        "bike_sharing",
        "2011-06-01",
        columns,
        "s3://b/predictions/ref_date=2011-06-01/",
    )

    glue.update_partition.assert_called_once()


@patch("glue_catalog_predictions.infer_glue_columns_from_parquet")
def test_register_predictions_table_end_to_end(mock_infer) -> None:
    mock_infer.return_value = [
        {"Name": "dteday", "Type": "string"},
        {"Name": "cnt_real", "Type": "bigint"},
        {"Name": "cnt_pred", "Type": "double"},
    ]
    glue = _mock_glue_client()
    glue.get_database.return_value = {"Database": {"Name": "bike_sharing"}}
    glue.get_table.side_effect = glue.exceptions.EntityNotFoundException()

    result = register_predictions_table(
        "s3://my-bucket/raw/day.csv",
        "2011-06-01",
        glue_client=glue,
    )

    assert result["qualified_name"] == "bike_sharing.predictions"
    assert result["ref_date"] == "2011-06-01"
    assert result["partition_location"] == "s3://my-bucket/predictions/ref_date=2011-06-01/"
    glue.create_table.assert_called_once()
    glue.create_partition.assert_called_once()
