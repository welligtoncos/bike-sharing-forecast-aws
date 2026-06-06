"""
S3-01 — Glue Job: treino XGBoost a partir de features.parquet.

Propósito
---------
Entry point Glue que invoca train_and_evaluate() do módulo xgboost_training.py.

Pré-requisito
-------------
  Executar antes o job validate_day_csv para o mesmo ref_date, gerando:
  s3://{bucket}/features/{ref_date}/features.parquet

Argumentos Glue
---------------
  --s3_input_path  URI S3 do day.csv (deriva bucket para features e metrics)
  --ref_date       Data de referência YYYY-MM-DD (partição features/metrics)

Saídas
------
  CloudWatch: RMSE=... MAE=...
  S3: s3://{bucket}/metrics/{ref_date}/metrics.json
  stdout Glue: rmse, mae, metrics_json
"""

from __future__ import annotations

import logging
import sys

from awsglue.utils import getResolvedOptions

# xgboost_training.py + schema_validation.py via --extra-py-files no Terraform.
from xgboost_training import train_and_evaluate

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    """Lê argumentos, treina modelo e imprime métricas no stdout."""
    args = getResolvedOptions(sys.argv, ["s3_input_path", "ref_date"])
    s3_input_path = args["s3_input_path"]
    ref_date = args["ref_date"]

    logger.info("s3_input_path=%s", s3_input_path)
    logger.info("ref_date=%s", ref_date)

    metrics = train_and_evaluate(s3_input_path, ref_date)

    # Resumo para validação manual no console Glue → Job runs → Output.
    print(f"s3_input_path: {s3_input_path}")
    print(f"ref_date: {ref_date}")
    print(f"rmse: {metrics['rmse']:.4f}")
    print(f"mae: {metrics['mae']:.4f}")
    print(f"metrics_json: {metrics['metrics_json']}")


if __name__ == "__main__":
    main()
