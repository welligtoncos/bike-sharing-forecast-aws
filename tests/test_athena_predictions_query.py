"""Testes S4-02 — query Athena de validacao de predicoes."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from athena_predictions_query import (  # noqa: E402
    build_predictions_validation_query,
    build_predictions_validation_query_stepfunctions_format,
    validate_ref_date,
)


def test_build_predictions_validation_query_has_four_columns_and_order() -> None:
    sql = build_predictions_validation_query("2011-06-01")

    assert "dteday" in sql
    assert "cnt_real" in sql
    assert "cnt_pred" in sql
    assert "ABS(cnt_real - cnt_pred) AS abs_error" in sql
    assert "WHERE ref_date = '2011-06-01'" in sql
    assert "ORDER BY dteday ASC" in sql
    assert sql.index("ORDER BY") > sql.index("WHERE")


def test_build_predictions_validation_query_custom_database() -> None:
    sql = build_predictions_validation_query("2012-01-01", database_name="bike_sharing")

    assert "FROM `bike_sharing`.predictions" in sql
    assert "ref_date = '2012-01-01'" in sql


def test_validate_ref_date_rejects_invalid_format() -> None:
    with pytest.raises(ValueError, match="ref_date invalido"):
        validate_ref_date("06-2011-01")

    with pytest.raises(ValueError, match="ref_date invalido"):
        validate_ref_date("2011/06/01")


def test_stepfunctions_format_template_uses_placeholder() -> None:
    template = build_predictions_validation_query_stepfunctions_format()

    assert "{}" in template
    assert "abs_error" in template
    assert "ORDER BY dteday ASC" in template
