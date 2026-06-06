"""
S1-02 - Glue Job Python Shell: leitura de argumentos do Step Functions.

Argumentos esperados (via getResolvedOptions):
  --ref_date       Data de referencia do pipeline (ex.: 2024-06-01)
  --s3_input_path  Caminho S3 de entrada (ex.: s3://bucket/raw/ibovespa.csv)

Step Functions sobrescreve estes valores em JobRun Arguments; os defaults
vem do default_arguments do aws_glue_job no Terraform.

Nota: em Python Shell, JOB_NAME nao e injetado em sys.argv — nao incluir em
getResolvedOptions (diferente de Glue ETL/Spark).
"""

import logging
import sys

from awsglue.utils import getResolvedOptions

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    args = getResolvedOptions(
        sys.argv,
        [
            "ref_date",
            "s3_input_path",
        ],
    )

    ref_date = args["ref_date"]
    s3_input_path = args["s3_input_path"]

    logger.info("ref_date=%s", ref_date)
    logger.info("s3_input_path=%s", s3_input_path)

    print(f"ref_date: {ref_date}")
    print(f"s3_input_path: {s3_input_path}")


if __name__ == "__main__":
    main()
