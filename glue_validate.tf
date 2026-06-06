# =============================================================================
# S2-01 — Glue Job: validacao de schema day.csv
# =============================================================================

resource "aws_s3_object" "glue_module_schema_validation" {
  bucket = aws_s3_bucket.pipeline.id
  key    = local.glue_module_schema_validation_key
  source = "${path.module}/scripts/schema_validation.py"
  etag   = filemd5("${path.module}/scripts/schema_validation.py")

  tags = {
    Name = local.glue_module_schema_validation_key
  }
}

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
  max_capacity = 0.0625
  timeout      = 10
  max_retries  = 0

  command {
    name            = "pythonshell"
    script_location = "s3://${aws_s3_bucket.pipeline.id}/${local.glue_script_validate_day_csv_key}"
    python_version  = "3.9"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--enable-continuous-cloudwatch-log" = "true"
    "--extra-py-files"                   = "s3://${aws_s3_bucket.pipeline.id}/${local.glue_module_schema_validation_key}"
    "--additional-python-modules"        = "s3fs"
    "--s3_input_path"                    = local.s3_input_day_csv_path
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
