"""
S4-01 — Registro da tabela predictions no Glue Catalog (partição ref_date).

Propósito
---------
Lê um Parquet de predições no S3, infere o schema (dteday, cnt_real, cnt_pred)
e cria/atualiza a tabela Glue ``bike_sharing.predictions`` com partição
``ref_date`` — consultável no Athena.

Layout S3 esperado (Hive-style)
--------------------------------
  s3://{bucket}/predictions/ref_date={ref_date}/predictions.parquet

Lake Formation
--------------
O database ``bike_sharing`` é provisionado no Terraform; permissões LF opcionais
via ``enable_lake_formation``. O registro da tabela/partição usa boto3 Glue API.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence
from urllib.parse import urlparse

import boto3
import pandas as pd
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

DATABASE_NAME_DEFAULT = "bike_sharing"
TABLE_NAME = "predictions"
PARTITION_KEY = "ref_date"
PREDICTIONS_PARQUET_NAME = "predictions.parquet"

REQUIRED_COLUMNS: tuple[str, ...] = ("dteday", "cnt_real", "cnt_pred")

PARQUET_INPUT_FORMAT = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
PARQUET_OUTPUT_FORMAT = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"
PARQUET_SERDE_INFO: dict[str, Any] = {
    "SerializationLibrary": "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe",
    "Parameters": {"serialization.format": "1"},
}


def _parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    parsed = urlparse(s3_uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError(f"Caminho S3 invalido (esperado s3://...): {s3_uri}")
    key = parsed.path.lstrip("/")
    return parsed.netloc, key


def _bucket_from_s3_input_path(s3_input_path: str) -> str:
    bucket, _ = _parse_s3_uri(s3_input_path)
    return bucket


def predictions_table_root_uri(s3_input_path: str) -> str:
    """Raiz EXTERNAL TABLE — particoes ficam em ref_date=... abaixo deste prefixo."""
    bucket = _bucket_from_s3_input_path(s3_input_path)
    return f"s3://{bucket}/predictions/"


def predictions_parquet_uri(s3_input_path: str, ref_date: str) -> str:
    """URI do Parquet de predições para inferencia de schema."""
    bucket = _bucket_from_s3_input_path(s3_input_path)
    return f"s3://{bucket}/predictions/ref_date={ref_date}/{PREDICTIONS_PARQUET_NAME}"


def predictions_partition_location(s3_input_path: str, ref_date: str) -> str:
    """Local S3 da particao registrada no Glue Catalog."""
    bucket = _bucket_from_s3_input_path(s3_input_path)
    return f"s3://{bucket}/predictions/ref_date={ref_date}/"


def pandas_dtype_to_glue(dtype: Any) -> str:
    """Mapeia dtype pandas para tipo Hive/Glue."""
    if pd.api.types.is_integer_dtype(dtype):
        return "bigint"
    if pd.api.types.is_float_dtype(dtype):
        return "double"
    if pd.api.types.is_bool_dtype(dtype):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "timestamp"
    return "string"


def infer_glue_columns_from_parquet(s3_uri: str) -> list[dict[str, str]]:
    """
    Infere colunas Glue a partir do Parquet (via pandas/pyarrow).

    Valida presença de dteday, cnt_real, cnt_pred.
    """
    if not s3_uri.startswith("s3://"):
        raise ValueError(f"Caminho S3 invalido (esperado s3://...): {s3_uri}")

    try:
        df = pd.read_parquet(s3_uri, engine="pyarrow")
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Parquet de predicoes nao encontrado: {s3_uri}. "
            "Gere antes com: python scripts/generate_sample_predictions.py "
            f"--s3_input_path <raw/day.csv> --ref_date <YYYY-MM-DD>"
        ) from exc
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        if len(missing) == 1:
            raise ValueError(f"Coluna ausente no schema: '{missing[0]}'")
        names = ", ".join(f"'{column}'" for column in missing)
        raise ValueError(f"Colunas ausentes no schema: {names}")

    columns = [
        {"Name": column, "Type": pandas_dtype_to_glue(df[column].dtype)}
        for column in REQUIRED_COLUMNS
    ]
    logger.info("Schema inferido de %s: %s", s3_uri, columns)
    return columns


def _parquet_storage_descriptor(columns: Sequence[dict[str, str]], location: str) -> dict[str, Any]:
    return {
        "Columns": list(columns),
        "Location": location,
        "InputFormat": PARQUET_INPUT_FORMAT,
        "OutputFormat": PARQUET_OUTPUT_FORMAT,
        "SerdeInfo": PARQUET_SERDE_INFO,
    }


def ensure_database(
    glue_client: Any,
    database_name: str,
    *,
    description: str = "Bike Sharing pipeline — Lake Formation",
    location_uri: str | None = None,
) -> None:
    """Cria database Glue se ainda nao existir (idempotente)."""
    try:
        glue_client.get_database(Name=database_name)
        logger.info("Database Glue '%s' ja existe.", database_name)
        return
    except glue_client.exceptions.EntityNotFoundException:
        pass

    database_input: dict[str, Any] = {
        "Name": database_name,
        "Description": description,
    }
    if location_uri:
        database_input["LocationUri"] = location_uri

    glue_client.create_database(DatabaseInput=database_input)
    logger.info("Database Glue '%s' criado.", database_name)


def create_or_update_table(
    glue_client: Any,
    database_name: str,
    columns: Sequence[dict[str, str]],
    table_location: str,
    *,
    table_name: str = TABLE_NAME,
) -> None:
    """Cria ou atualiza tabela EXTERNAL particionada por ref_date."""
    table_input: dict[str, Any] = {
        "Name": table_name,
        "TableType": "EXTERNAL_TABLE",
        "Parameters": {
            "classification": "parquet",
            "EXTERNAL": "TRUE",
        },
        "PartitionKeys": [{"Name": PARTITION_KEY, "Type": "string"}],
        "StorageDescriptor": _parquet_storage_descriptor(columns, table_location),
    }

    try:
        glue_client.get_table(DatabaseName=database_name, Name=table_name)
        glue_client.update_table(
            DatabaseName=database_name,
            TableInput=table_input,
        )
        logger.info("Tabela %s.%s atualizada.", database_name, table_name)
    except glue_client.exceptions.EntityNotFoundException:
        glue_client.create_table(DatabaseName=database_name, TableInput=table_input)
        logger.info("Tabela %s.%s criada.", database_name, table_name)


def register_partition(
    glue_client: Any,
    database_name: str,
    ref_date: str,
    columns: Sequence[dict[str, str]],
    partition_location: str,
    *,
    table_name: str = TABLE_NAME,
) -> None:
    """Registra (ou atualiza) particao ref_date no Glue Catalog."""
    partition_input: dict[str, Any] = {
        "Values": [ref_date],
        "StorageDescriptor": _parquet_storage_descriptor(columns, partition_location),
    }

    try:
        glue_client.create_partition(
            DatabaseName=database_name,
            TableName=table_name,
            PartitionInput=partition_input,
        )
        logger.info(
            "Particao %s=%s registrada em %s.",
            PARTITION_KEY,
            ref_date,
            partition_location,
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "AlreadyExistsException":
            raise
        glue_client.update_partition(
            DatabaseName=database_name,
            TableName=table_name,
            PartitionValueList=[ref_date],
            PartitionInput=partition_input,
        )
        logger.info(
            "Particao %s=%s atualizada em %s.",
            PARTITION_KEY,
            ref_date,
            partition_location,
        )


def register_predictions_table(
    s3_input_path: str,
    ref_date: str,
    *,
    database_name: str = DATABASE_NAME_DEFAULT,
    predictions_parquet_path: str | None = None,
    glue_client: Any | None = None,
) -> dict[str, str]:
    """
    Orquestra S4-01: inferir schema, criar/atualizar tabela e registrar particao.

    Returns:
        Dict com database, table, partition e URIs S3.
    """
    glue = glue_client or boto3.client("glue")

    parquet_uri = predictions_parquet_path or predictions_parquet_uri(s3_input_path, ref_date)
    columns = infer_glue_columns_from_parquet(parquet_uri)

    table_root = predictions_table_root_uri(s3_input_path)
    partition_loc = predictions_partition_location(s3_input_path, ref_date)

    ensure_database(
        glue,
        database_name,
        location_uri=table_root,
    )
    create_or_update_table(glue, database_name, columns, table_root)
    register_partition(glue, database_name, ref_date, columns, partition_loc)

    qualified = f"{database_name}.{TABLE_NAME}"

    logger.info("Tabela %s registrada; particao ref_date=%s.", qualified, ref_date)

    return {
        "database": database_name,
        "table": TABLE_NAME,
        "qualified_name": qualified,
        "ref_date": ref_date,
        "predictions_parquet": parquet_uri,
        "partition_location": partition_loc,
        "table_location": table_root,
    }
