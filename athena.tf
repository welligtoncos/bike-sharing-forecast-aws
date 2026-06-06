# =============================================================================
# S4-02 — Athena workgroup + Step Functions validate predictions
# =============================================================================

resource "aws_athena_workgroup" "pipeline" {
  name = local.athena_workgroup_name

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true

    result_configuration {
      output_location = "s3://${aws_s3_bucket.pipeline.id}/${local.athena_results_prefix}"
    }
  }

  tags = {
    Name = local.athena_workgroup_name
  }
}

resource "aws_sfn_state_machine" "validate_predictions" {
  provider = aws.no_default_tags
  name     = local.sfn_validate_predictions_name
  role_arn = aws_iam_role.stepfunctions.arn

  definition = templatefile("${path.module}/stepfunctions/validate_predictions.asl.json.tpl", {
    database_name         = var.glue_predictions_db_name
    athena_workgroup_name = aws_athena_workgroup.pipeline.name
  })

  depends_on = [
    aws_iam_role_policy.stepfunctions_athena,
    aws_athena_workgroup.pipeline,
    aws_glue_catalog_database.bike_sharing,
  ]
}
