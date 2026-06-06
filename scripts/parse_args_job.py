"""
S1-02 — Glue Job Python Shell: leitura de argumentos do Step Functions.

Propósito
---------
Primeiro job do pipeline. Recebe os parâmetros que o Step Functions monta
e apenas valida/loga — prova que a orquestração consegue passar argumentos
dinâmicos ao Glue antes dos jobs de processamento (S2, S3).

Argumentos (via getResolvedOptions)
----------------------------------
  --ref_date       Data de referência do pipeline (ex.: 2011-06-01)
  --s3_input_path  Caminho S3 de entrada (ex.: s3://bucket/raw/day.csv)

Origem dos valores
------------------
  - Step Functions sobrescreve via JobRun Arguments na execução.
  - Terraform define defaults em aws_glue_job.default_arguments.

Nota importante (Python Shell)
------------------------------
  JOB_NAME não é injetado em sys.argv — não incluir em getResolvedOptions
  (diferente de Glue ETL/Spark, onde JOB_NAME costuma estar disponível).

Saída
-----
  Logs INFO no CloudWatch + print no stdout (visível no console Glue Runs).
"""

import logging
import sys

from awsglue.utils import getResolvedOptions

# Logger raiz do job; CloudWatch captura via --enable-continuous-cloudwatch-log.
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    """Ponto de entrada: lê argumentos Glue e registra no log."""
    # getResolvedOptions falha com exit code 2 se algum argumento listado estiver ausente.
    args = getResolvedOptions(
        sys.argv,
        [
            "ref_date",
            "s3_input_path",
        ],
    )

    ref_date = args["ref_date"]
    s3_input_path = args["s3_input_path"]

    # CloudWatch — formato estruturado facilita busca por ref_date no console.
    logger.info("ref_date=%s", ref_date)
    logger.info("s3_input_path=%s", s3_input_path)

    # print aparece também na aba Output do Glue Job Run (útil para debug rápido).
    print(f"ref_date: {ref_date}")
    print(f"s3_input_path: {s3_input_path}")


if __name__ == "__main__":
    main()
