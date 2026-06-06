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
    "metrics/",      # metricas de treino (RMSE, MAE) por ref_date
    "predictions/",  # resultados inferencia do modelo
    "models/",       # artefatos do modelo treinado
    "athena-results/", # saida de queries Athena (S4-02)
  ])

  iam_role_glue = "${local.name_prefix}-iam-glue"

  # S1-02 — Glue Job Python Shell
  glue_job_parse_args_name   = "${local.name_prefix}-glue-job-parse-args"
  glue_script_parse_args_key = "scripts/parse_args_job.py"

  # S2-01 — Glue Job validacao schema day.csv
  glue_job_validate_day_csv_name   = "${local.name_prefix}-glue-job-validate-day-csv"
  glue_script_validate_day_csv_key = "scripts/validate_day_csv_job.py"
  glue_module_schema_validation_key = "scripts/schema_validation.py"

  # S3-01 — Glue Job treino XGBoost
  glue_job_train_xgboost_name        = "${local.name_prefix}-glue-job-train-xgboost"
  glue_script_train_xgboost_key      = "scripts/train_xgboost_job.py"
  glue_module_xgboost_training_key   = "scripts/xgboost_training.py"

  # S4-01 — Glue Catalog predictions (bike_sharing)
  glue_job_register_predictions_catalog_name   = "${local.name_prefix}-glue-job-register-predictions-catalog"
  glue_script_register_predictions_catalog_key = "scripts/register_predictions_catalog_job.py"
  glue_module_catalog_predictions_key          = "scripts/glue_catalog_predictions.py"

  # S4-02 — Athena validacao predictions
  athena_workgroup_name        = "${local.name_prefix}-athena-pipeline"
  athena_results_prefix        = "athena-results/"
  sfn_validate_predictions_name = "${local.name_prefix}-sfn-validate-predictions"

  glue_catalog_arn  = "arn:aws:glue:${var.aws_region}:${var.aws_account_id}:catalog"
  glue_database_arn = "arn:aws:glue:${var.aws_region}:${var.aws_account_id}:database/${var.glue_db_name}"
  glue_table_arns = [
    "arn:aws:glue:${var.aws_region}:${var.aws_account_id}:table/${var.glue_db_name}/*",
  ]
  glue_predictions_database_arn = "arn:aws:glue:${var.aws_region}:${var.aws_account_id}:database/${var.glue_predictions_db_name}"
  glue_predictions_table_arns = [
    "arn:aws:glue:${var.aws_region}:${var.aws_account_id}:table/${var.glue_predictions_db_name}/*",
  ]
  glue_job_log_group_arn        = "arn:aws:logs:${var.aws_region}:${var.aws_account_id}:log-group:/aws-glue/python-jobs"
  glue_job_log_group_stream_arn = "${local.glue_job_log_group_arn}:*"

  # S1-03 — Step Functions mensal
  s3_input_day_csv_path              = "s3://${local.s3_bucket_name}/raw/day.csv"
  sfn_monthly_pipeline_name          = "${local.name_prefix}-sfn-monthly-pipeline"
  sns_pipeline_alerts_name           = "${local.name_prefix}-sns-pipeline-alerts"
  eventbridge_monthly_pipeline_name  = "${local.name_prefix}-eventbridge-monthly-pipeline"
  iam_role_stepfunctions             = "${local.name_prefix}-iam-stepfunctions"
  iam_role_eventbridge_sfn           = "${local.name_prefix}-iam-eventbridge-sfn"

  # SNS: topico pre-existente (evita sns:ListTagsForResource no refresh do provider)
  sns_topic_arn = var.sns_pipeline_alerts_arn != "" ? var.sns_pipeline_alerts_arn : "arn:aws:sns:${var.aws_region}:${var.aws_account_id}:${local.sns_pipeline_alerts_name}"

  features_parquet_uri_template    = "s3://${local.s3_bucket_name}/features/{ref_date}/features.parquet"
  metrics_json_uri_template        = "s3://${local.s3_bucket_name}/metrics/{ref_date}/metrics.json"
  predictions_parquet_uri_template = "s3://${local.s3_bucket_name}/predictions/ref_date={ref_date}/predictions.parquet"
}
