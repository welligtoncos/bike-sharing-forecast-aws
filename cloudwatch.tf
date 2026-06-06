# =============================================================================
# S4-03 — CloudWatch: alarmes, metric filters e dashboard do pipeline
# =============================================================================
#
# Conta usuario-dados (IAM limitada):
#   create_cloudwatch_alarms            = false  — sem cloudwatch:ListTagsForResource
#   create_cloudwatch_log_metric_filter = false  — sem logs:PutMetricFilter
#   create_cloudwatch_dashboard         = false  — sem cloudwatch:PutDashboard
#
# Com flags false, crie alarmes/dashboard uma vez via CLI (docs/s4-03).
# O dashboard referencia ARNs construidos pelo nome padrao dos alarmes.
# Falha Glue: metrica GlueJobFailure publicada pelo job (pipeline_observability.py).

locals {
  cloudwatch_alarm_glue_job_failure_arn = "arn:aws:cloudwatch:${var.aws_region}:${var.aws_account_id}:alarm:${local.name_prefix}-alarm-glue-job-failure"
  cloudwatch_alarm_rmse_threshold_arn   = "arn:aws:cloudwatch:${var.aws_region}:${var.aws_account_id}:alarm:${local.name_prefix}-alarm-rmse-threshold"
}

resource "aws_cloudwatch_log_metric_filter" "glue_job_traceback" {
  count = var.create_cloudwatch_log_metric_filter ? 1 : 0

  name           = "${local.name_prefix}-glue-job-traceback"
  log_group_name = "/aws-glue/python-jobs"
  pattern        = "Traceback (most recent call last)"

  metric_transformation {
    name          = "GlueJobLogFailure"
    namespace     = local.cloudwatch_pipeline_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_metric_alarm" "glue_job_failure" {
  count = var.create_cloudwatch_alarms ? 1 : 0

  provider = aws.no_default_tags

  alarm_name          = "${local.name_prefix}-alarm-glue-job-failure"
  alarm_description   = "Glue Job falhou (metrica custom GlueJobFailure publicada pelo job)."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "GlueJobFailure"
  namespace           = local.cloudwatch_pipeline_namespace
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  treat_missing_data  = "notBreaching"

  alarm_actions = [local.sns_topic_arn]
  ok_actions    = [local.sns_topic_arn]
}

resource "aws_cloudwatch_metric_alarm" "rmse_threshold" {
  count = var.create_cloudwatch_alarms ? 1 : 0

  provider = aws.no_default_tags

  alarm_name          = "${local.name_prefix}-alarm-rmse-threshold"
  alarm_description   = "RMSE do mes excedeu threshold (metrica RMSEThresholdBreached)."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "RMSEThresholdBreached"
  namespace           = local.cloudwatch_pipeline_namespace
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  treat_missing_data  = "notBreaching"

  alarm_actions = [local.sns_topic_arn]
  ok_actions    = [local.sns_topic_arn]
}

resource "aws_cloudwatch_dashboard" "pipeline" {
  count = var.create_cloudwatch_dashboard ? 1 : 0

  dashboard_name = "${local.name_prefix}-pipeline-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "text"
        x      = 0
        y      = 0
        width  = 24
        height = 2
        properties = {
          markdown = "# Pipeline Bike Sharing — metricas CloudWatch (S4-03)\nNamespace: `${local.cloudwatch_pipeline_namespace}`"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 2
        width  = 12
        height = 6
        properties = {
          title  = "RMSE e MAE por execucao"
          region = var.aws_region
          view   = "timeSeries"
          stat   = "Maximum"
          period = 300
          metrics = [
            [local.cloudwatch_pipeline_namespace, "RMSE"],
            [".", "MAE"],
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 2
        width  = 12
        height = 6
        properties = {
          title  = "Alarmes — falha Glue e RMSE threshold"
          region = var.aws_region
          view   = "timeSeries"
          stat   = "Sum"
          period = 300
          metrics = concat(
            [
              [local.cloudwatch_pipeline_namespace, "RMSEThresholdBreached"],
              [".", "GlueJobFailure"],
            ],
            var.create_cloudwatch_log_metric_filter ? [[local.cloudwatch_pipeline_namespace, "GlueJobLogFailure"]] : [],
          )
        }
      },
      {
        type   = "alarm"
        x      = 0
        y      = 8
        width  = 24
        height = 4
        properties = {
          title  = "Status dos alarmes"
          alarms = [
            local.cloudwatch_alarm_glue_job_failure_arn,
            local.cloudwatch_alarm_rmse_threshold_arn,
          ]
        }
      },
    ]
  })
}
