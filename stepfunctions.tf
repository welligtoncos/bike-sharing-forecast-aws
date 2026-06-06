# =============================================================================
# S1-03 — Step Functions + EventBridge + SNS
# =============================================================================
#
# Agenda execucao mensal (dia 1) que:
#   1. Calcula ref_date = YYYY-MM-01 (mes corrente)
#   2. Define s3_input_path = s3://{bucket}/raw/day.csv
#   3. Invoca Glue Job via startJobRun.sync
#   4. Em falha, publica alerta SNS
#
# SNS: por padrao usa topico pre-existente (local.sns_topic_arn) para contas
# onde o operador Terraform nao tem sns:ListTagsForResource.
#
# ASL: stepfunctions/monthly_pipeline.asl.json.tpl
# =============================================================================

resource "aws_sns_topic" "pipeline_alerts" {
  count = var.create_sns_topic ? 1 : 0

  provider = aws.no_default_tags
  name     = local.sns_pipeline_alerts_name
}

# Inscricao e-mail: criar manualmente se o operador nao tem sns:GetSubscriptionAttributes:
#   aws sns subscribe --topic-arn <arn> --protocol email --notification-endpoint <email>

resource "aws_sfn_state_machine" "monthly_pipeline" {
  provider = aws.no_default_tags
  name     = local.sfn_monthly_pipeline_name
  role_arn = aws_iam_role.stepfunctions.arn

  definition = templatefile("${path.module}/stepfunctions/monthly_pipeline.asl.json.tpl", {
    s3_input_path = local.s3_input_day_csv_path
    glue_job_name = local.glue_job_parse_args_name
    sns_topic_arn = local.sns_topic_arn
    name_prefix   = local.name_prefix
  })

  depends_on = [
    aws_iam_role_policy.stepfunctions_glue_sns,
    aws_glue_job.parse_args,
  ]
}

resource "aws_cloudwatch_event_rule" "monthly_pipeline" {
  count = var.create_eventbridge_schedule ? 1 : 0

  provider            = aws.no_default_tags
  name                = local.eventbridge_monthly_pipeline_name
  description         = "Dispara Step Functions do pipeline no dia 1 de cada mes (06:00 UTC)."
  schedule_expression = var.monthly_pipeline_schedule
  state               = var.monthly_pipeline_enabled ? "ENABLED" : "DISABLED"
}

resource "aws_cloudwatch_event_target" "monthly_pipeline" {
  count = var.create_eventbridge_schedule ? 1 : 0

  provider  = aws.no_default_tags
  rule      = aws_cloudwatch_event_rule.monthly_pipeline[0].name
  target_id = "monthly-pipeline-sfn"
  arn       = aws_sfn_state_machine.monthly_pipeline.arn
  role_arn  = aws_iam_role.eventbridge_sfn.arn
}
