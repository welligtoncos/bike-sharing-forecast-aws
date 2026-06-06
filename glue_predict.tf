# =============================================================================
# S3-03 — Glue Job: inferência XGBoost → predictions.parquet
# =============================================================================

resource "aws_s3_object" "glue_script_predict_xgboost" {
  bucket = aws_s3_bucket.pipeline.id
  key    = local.glue_script_predict_xgboost_key
  source = "${path.module}/scripts/predict_xgboost_job.py"
  etag   = filemd5("${path.module}/scripts/predict_xgboost_job.py")

  tags = {
    Name = local.glue_script_predict_xgboost_key
  }
}

resource "aws_s3_object" "glue_module_xgboost_inference" {
  bucket = aws_s3_bucket.pipeline.id
  key    = local.glue_module_xgboost_inference_key
  source = "${path.module}/scripts/xgboost_inference.py"
  etag   = filemd5("${path.module}/scripts/xgboost_inference.py")

  tags = {
    Name = local.glue_module_xgboost_inference_key
  }
}

resource "aws_glue_job" "predict_xgboost" {
  name         = local.glue_job_predict_xgboost_name
  role_arn     = aws_iam_role.glue.arn
  glue_version = "3.0"
  max_capacity = 0.0625
  timeout      = 15
  max_retries  = 0

  command {
    name            = "pythonshell"
    script_location = "s3://${aws_s3_bucket.pipeline.id}/${local.glue_script_predict_xgboost_key}"
    python_version  = "3.9"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--enable-continuous-cloudwatch-log" = "true"
    "--extra-py-files" = join(",", [
      "s3://${aws_s3_bucket.pipeline.id}/${local.glue_module_schema_validation_key}",
      "s3://${aws_s3_bucket.pipeline.id}/${local.glue_module_xgboost_training_key}",
      "s3://${aws_s3_bucket.pipeline.id}/${local.glue_module_xgboost_inference_key}",
      "s3://${aws_s3_bucket.pipeline.id}/${local.glue_module_catalog_predictions_key}",
      "s3://${aws_s3_bucket.pipeline.id}/${local.glue_module_pipeline_observability_key}",
    ])
    "--additional-python-modules" = "s3fs,pyarrow,xgboost,scikit-learn,joblib"
    "--s3_input_path"               = local.s3_input_day_csv_path
    "--ref_date"                    = "1970-01-01"
  }

  tags = {
    Name = local.glue_job_predict_xgboost_name
  }

  depends_on = [
    aws_s3_object.glue_module_schema_validation,
    aws_s3_object.glue_module_xgboost_training,
    aws_s3_object.glue_module_xgboost_inference,
    aws_s3_object.glue_module_catalog_predictions,
    aws_s3_object.glue_module_pipeline_observability,
    aws_s3_object.glue_script_predict_xgboost,
    aws_iam_role_policy_attachment.glue_service,
    aws_iam_role_policy.glue_s3,
    aws_iam_role_policy.glue_catalog,
    aws_iam_role_policy.glue_cloudwatch_metrics,
    aws_iam_role_policy.glue_logs,
  ]
}
