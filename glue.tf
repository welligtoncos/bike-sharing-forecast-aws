# =============================================================================
# S1-02 — Glue Job Python Shell (argumentos Step Functions)
# =============================================================================
#
# Job leve (Python Shell) que recebe --ref_date e --s3_input_path via
# getResolvedOptions e registra os valores no CloudWatch Logs.
#
# Step Functions invoca com Arguments sobrescrevendo os defaults:
#   { "--ref_date": "2024-06-01", "--s3_input_path": "s3://.../raw/data.csv" }
#
# Script armazenado em s3://{bucket}/scripts/parse_args_job.py
# =============================================================================

resource "aws_s3_object" "glue_script_parse_args" {
  bucket = aws_s3_bucket.pipeline.id
  key    = local.glue_script_parse_args_key
  source = "${path.module}/scripts/parse_args_job.py"
  etag   = filemd5("${path.module}/scripts/parse_args_job.py")

  tags = {
    Name = local.glue_script_parse_args_key
  }
}

resource "aws_glue_job" "parse_args" {
  name         = local.glue_job_parse_args_name
  role_arn     = aws_iam_role.glue.arn
  glue_version = "3.0"
  max_capacity = 0.0625
  timeout      = 5
  max_retries  = 0

  command {
    name            = "pythonshell"
    script_location = "s3://${aws_s3_bucket.pipeline.id}/${local.glue_script_parse_args_key}"
    python_version  = "3.9"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--enable-continuous-cloudwatch-log" = "true"
    "--ref_date"                         = "1970-01-01"
    "--s3_input_path"                    = "s3://${aws_s3_bucket.pipeline.id}/raw/"
  }

  tags = {
    Name = local.glue_job_parse_args_name
  }

  depends_on = [
    aws_s3_object.glue_script_parse_args,
    aws_iam_role_policy_attachment.glue_service,
    aws_iam_role_policy.glue_s3,
    aws_iam_role_policy.glue_catalog,
    aws_iam_role_policy.glue_logs,
  ]
}
