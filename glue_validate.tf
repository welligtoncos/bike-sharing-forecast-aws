# =============================================================================
# S2-01 / S2-02 / S2-03 — Glue Job: validação, filtro e features Parquet
# =============================================================================
#
# Job Python Shell que executa validate_day_csv_job.py.
# Lógica de negócio em schema_validation.py (--extra-py-files).
#
# Entrada : s3://{bucket}/raw/day.csv + --ref_date
# Saída   : s3://{bucket}/features/{ref_date}/features.parquet
#
# Execução manual (exemplo):
#   aws glue start-job-run --job-name glue-b3-dev-glue-job-validate-day-csv \
#     --arguments '{"--ref_date":"2011-06-01","--s3_input_path":"s3://.../raw/day.csv"}'
# =============================================================================

# Módulo Python importado pelo job (from schema_validation import ...).
resource "aws_s3_object" "glue_module_schema_validation" {
  bucket = aws_s3_bucket.pipeline.id
  key    = local.glue_module_schema_validation_key
  source = "${path.module}/scripts/schema_validation.py"
  etag   = filemd5("${path.module}/scripts/schema_validation.py")

  tags = {
    Name = local.glue_module_schema_validation_key
  }
}

# Script principal — entry point registrado no Glue Job.
resource "aws_s3_object" "glue_script_validate_day_csv" {
  bucket = aws_s3_bucket.pipeline.id
  key    = local.glue_script_validate_day_csv_key
  source = "${path.module}/scripts/validate_day_csv_job.py"
  etag   = filemd5("${path.module}/scripts/validate_day_csv_job.py")

  tags = {
    Name = local.glue_script_validate_day_csv_key
  }
}

resource "aws_glue_job" "validate_day_csv" {
  name         = local.glue_job_validate_day_csv_name
  role_arn     = aws_iam_role.glue.arn
  glue_version = "3.0"
  max_capacity = 0.0625 # 1/16 DPU — suficiente para pandas em dataset pequeno
  timeout      = 10     # minutos
  max_retries  = 0      # falha visível imediatamente (SNS via Step Functions)

  command {
    name            = "pythonshell"
    script_location = "s3://${aws_s3_bucket.pipeline.id}/${local.glue_script_validate_day_csv_key}"
    python_version  = "3.9"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--enable-continuous-cloudwatch-log" = "true" # stdout/stderr → CloudWatch
    # schema_validation.py disponível no PYTHONPATH do job.
    "--extra-py-files" = "s3://${aws_s3_bucket.pipeline.id}/${local.glue_module_schema_validation_key}"
    # s3fs: pd.read_csv(s3://...); pyarrow: to_parquet no S3.
    "--additional-python-modules" = "s3fs,pyarrow"
    "--s3_input_path"               = local.s3_input_day_csv_path
    "--ref_date"                    = "1970-01-01" # placeholder — sobrescrito na execução
  }

  tags = {
    Name = local.glue_job_validate_day_csv_name
  }

  depends_on = [
    aws_s3_object.glue_module_schema_validation,
    aws_s3_object.glue_script_validate_day_csv,
    aws_iam_role_policy_attachment.glue_service,
    aws_iam_role_policy.glue_s3,
    aws_iam_role_policy.glue_catalog,
    aws_iam_role_policy.glue_logs,
  ]
}
