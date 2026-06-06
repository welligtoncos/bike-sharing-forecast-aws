# =============================================================================
# S3-01 — Glue Job: treino XGBoost com features Parquet
# =============================================================================
#
# Job Python Shell que executa train_xgboost_job.py.
# Lógica em xgboost_training.py; reutiliza schema_validation.py (constantes + URI).
#
# Pré-requisito: features Parquet do job validate_day_csv para o mesmo ref_date.
#
# Entrada : s3://{bucket}/features/{ref_date}/features.parquet (derivado)
# Saída   : s3://{bucket}/metrics/{ref_date}/metrics.json
#
# Execução manual (exemplo):
#   aws glue start-job-run --job-name glue-b3-dev-glue-job-train-xgboost \
#     --arguments '{"--ref_date":"2011-06-01","--s3_input_path":"s3://.../raw/day.csv"}'
# =============================================================================

resource "aws_s3_object" "glue_script_train_xgboost" {
  bucket = aws_s3_bucket.pipeline.id
  key    = local.glue_script_train_xgboost_key
  source = "${path.module}/scripts/train_xgboost_job.py"
  etag   = filemd5("${path.module}/scripts/train_xgboost_job.py")

  tags = {
    Name = local.glue_script_train_xgboost_key
  }
}

resource "aws_s3_object" "glue_module_xgboost_training" {
  bucket = aws_s3_bucket.pipeline.id
  key    = local.glue_module_xgboost_training_key
  source = "${path.module}/scripts/xgboost_training.py"
  etag   = filemd5("${path.module}/scripts/xgboost_training.py")

  tags = {
    Name = local.glue_module_xgboost_training_key
  }
}

resource "aws_s3_object" "glue_module_pipeline_observability" {
  bucket = aws_s3_bucket.pipeline.id
  key    = local.glue_module_pipeline_observability_key
  source = "${path.module}/scripts/pipeline_observability.py"
  etag   = filemd5("${path.module}/scripts/pipeline_observability.py")

  tags = {
    Name = local.glue_module_pipeline_observability_key
  }
}

resource "aws_glue_job" "train_xgboost" {
  name         = local.glue_job_train_xgboost_name
  role_arn     = aws_iam_role.glue.arn
  glue_version = "3.0"
  max_capacity = 0.0625
  timeout      = 15 # XGBoost + pip install modules pode levar mais que validate
  max_retries  = 0

  command {
    name            = "pythonshell"
    script_location = "s3://${aws_s3_bucket.pipeline.id}/${local.glue_script_train_xgboost_key}"
    python_version  = "3.9"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--enable-continuous-cloudwatch-log" = "true"
    # Dois módulos: xgboost_training (treino) + schema_validation (FEATURE_COLUMNS, URIs).
    "--extra-py-files" = join(",", [
      "s3://${aws_s3_bucket.pipeline.id}/${local.glue_module_schema_validation_key}",
      "s3://${aws_s3_bucket.pipeline.id}/${local.glue_module_xgboost_training_key}",
      "s3://${aws_s3_bucket.pipeline.id}/${local.glue_module_pipeline_observability_key}",
    ])
    # xgboost/scikit-learn instalados no cold start; pyarrow/s3fs para Parquet S3.
    "--additional-python-modules" = "s3fs,pyarrow,xgboost,scikit-learn,joblib"
    "--s3_input_path"               = local.s3_input_day_csv_path
    "--ref_date"                    = "1970-01-01"
    "--rmse_threshold"              = tostring(var.rmse_threshold)
    "--cloudwatch_namespace"        = local.cloudwatch_pipeline_namespace
  }

  tags = {
    Name = local.glue_job_train_xgboost_name
  }

  depends_on = [
    aws_s3_object.glue_module_schema_validation,
    aws_s3_object.glue_module_xgboost_training,
    aws_s3_object.glue_module_pipeline_observability,
    aws_s3_object.glue_script_train_xgboost,
    aws_iam_role_policy_attachment.glue_service,
    aws_iam_role_policy.glue_s3,
    aws_iam_role_policy.glue_catalog,
    aws_iam_role_policy.glue_cloudwatch_metrics,
    aws_iam_role_policy.glue_logs,
  ]
}
