"""
S2-01 / S2-02 / S2-03 — Glue Job: validação, filtro e features Parquet.

Propósito
---------
Entry point executado pelo AWS Glue Python Shell. Delega a lógica de negócio
ao módulo schema_validation.py (enviado como --extra-py-files no Terraform).

Fluxo
-----
  raw/day.csv  →  validar schema  →  filtrar ref_date  →  features.parquet

Argumentos Glue
---------------
  --s3_input_path  URI S3 do day.csv (ex.: s3://bucket/raw/day.csv)
  --ref_date       Data de referência YYYY-MM-DD (filtra dteday por mês/ano)

Saídas possíveis
----------------
  - features_parquet: s3://.../features/{ref_date}/features.parquet
  - status: empty_no_records (mês sem dados — job termina com SUCCEEDED)
"""

from __future__ import annotations

import logging
import sys

from awsglue.utils import getResolvedOptions

# schema_validation.py é carregado via --extra-py-files (mesmo diretório lógico).
from schema_validation import process_and_save_features

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    """Executa o pipeline de features e imprime resultado no stdout do Glue."""
    args = getResolvedOptions(sys.argv, ["s3_input_path", "ref_date"])
    s3_input_path = args["s3_input_path"]
    ref_date = args["ref_date"]

    logger.info("s3_input_path=%s", s3_input_path)
    logger.info("ref_date=%s", ref_date)

    # None = mês vazio; job não falha (critério S2-02).
    output_uri = process_and_save_features(s3_input_path, ref_date)

    # Resumo visível na aba Output do Glue Job Run.
    print(f"s3_input_path: {s3_input_path}")
    print(f"ref_date: {ref_date}")

    if output_uri is None:
        print("status: empty_no_records")
        return

    print(f"features_parquet: {output_uri}")


if __name__ == "__main__":
    main()
