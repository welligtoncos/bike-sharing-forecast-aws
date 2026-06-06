# =============================================================================
# S4-03 — Step Functions: treino XGBoost com rmse_threshold parametrizavel
# =============================================================================

resource "aws_sfn_state_machine" "train_with_observability" {
  provider = aws.no_default_tags
  name     = local.sfn_train_with_observability_name
  role_arn = aws_iam_role.stepfunctions.arn

  definition = templatefile("${path.module}/stepfunctions/train_with_observability.asl.json.tpl", {
    glue_job_train_xgboost_name = aws_glue_job.train_xgboost.name
    s3_input_path             = local.s3_input_day_csv_path
    cloudwatch_namespace      = local.cloudwatch_pipeline_namespace
    rmse_threshold_default    = tostring(var.rmse_threshold)
    sns_topic_arn             = local.sns_topic_arn
    name_prefix               = local.name_prefix
  })

  depends_on = [
    aws_iam_role_policy.stepfunctions_glue_sns,
    aws_glue_job.train_xgboost,
  ]
}
