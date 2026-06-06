# =============================================================================
# Convencao de nomenclatura centralizada
# =============================================================================
#
# Padrao geral: {project_name}-{environment}-{aws_service}-{purpose}[-{account_id}]
#
# Exemplo (dev, conta 303238378103):
#   Bucket : glue-b3-dev-s3-pipeline-303238378103
#   IAM    : glue-b3-dev-iam-glue
#
# account_id entra apenas no nome do bucket (unicidade global na AWS).
# Demais recursos usam apenas name_prefix.
# =============================================================================

locals {
  name_prefix   = "${var.project_name}-${var.environment}"
  global_suffix = var.aws_account_id

  s3_bucket_name = "${local.name_prefix}-s3-pipeline-${local.global_suffix}"

  # Prefixos S3 do pipeline — cada pasta tem responsabilidade distinta no fluxo de dados.
  s3_folders = toset([
    "raw/",          # CSV original (ex.: ibovespa_stocks.csv)
    "features/",     # parquet/csv pos feature engineering
    "predictions/",  # resultados inferencia do modelo
    "models/",       # artefatos do modelo treinado
  ])

  iam_role_glue = "${local.name_prefix}-iam-glue"
}
