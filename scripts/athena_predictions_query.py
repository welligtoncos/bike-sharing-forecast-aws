"""
S4-02 — Query Athena para validar predições (dteday, cnt_real, cnt_pred, abs_error).

Uso
---
  from athena_predictions_query import build_predictions_validation_query

  sql = build_predictions_validation_query("2011-06-01")
  # Executar no Athena ou via Step Functions (validate_predictions.asl)
"""

from __future__ import annotations

import re

REF_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATABASE_NAME_DEFAULT = "bike_sharing"


def validate_ref_date(ref_date: str) -> str:
    """Valida formato YYYY-MM-DD (evita injeção SQL em parametros)."""
    if not REF_DATE_PATTERN.match(ref_date):
        raise ValueError(
            f"ref_date invalido (esperado YYYY-MM-DD): {ref_date!r}"
        )
    return ref_date


def build_predictions_validation_query(
    ref_date: str,
    *,
    database_name: str = DATABASE_NAME_DEFAULT,
) -> str:
    """
    Monta SQL Athena: 4 colunas + filtro ref_date + ORDER BY dteday ASC.

    Args:
        ref_date: Particao Hive (ex.: 2011-06-01).
        database_name: Glue database (default bike_sharing).
    """
    safe_ref_date = validate_ref_date(ref_date)
    safe_db = database_name.replace("`", "")

    return f"""SELECT
    dteday,
    cnt_real,
    cnt_pred,
    ABS(cnt_real - cnt_pred) AS abs_error
FROM `{safe_db}`.predictions
WHERE ref_date = '{safe_ref_date}'
ORDER BY dteday ASC"""


def build_predictions_validation_query_stepfunctions_format(
    database_name: str = DATABASE_NAME_DEFAULT,
) -> str:
    """
    Template States.Format para Step Functions — {} substituido por $.ref_date.

    Exemplo ASL:
      "query_string.$": "States.Format('...', $.ref_date)"
    """
    safe_db = database_name.replace("`", "")
    # Aspas simples escapadas para JSON/States.Format; {} = placeholder ref_date.
    return (
        f"SELECT dteday, cnt_real, cnt_pred, "
        f"ABS(cnt_real - cnt_pred) AS abs_error "
        f"FROM `{safe_db}`.predictions "
        f"WHERE ref_date = '{{}}' "
        f"ORDER BY dteday ASC"
    )
