# =============================================================================
# S1-03 — IAM: Step Functions e EventBridge
# =============================================================================

resource "aws_iam_role" "stepfunctions" {
  name = local.iam_role_stepfunctions

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = "sts:AssumeRole"
        Principal = {
          Service = "states.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = local.iam_role_stepfunctions
  }
}

resource "aws_iam_role_policy" "stepfunctions_glue_sns" {
  name = "${local.name_prefix}-sfn-glue-sns"
  role = aws_iam_role.stepfunctions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "StartAndMonitorGlueJob"
        Effect = "Allow"
        Action = [
          "glue:StartJobRun",
          "glue:GetJobRun",
          "glue:GetJobRuns",
          "glue:BatchStopJobRun",
        ]
        Resource = aws_glue_job.parse_args.arn
      },
      {
        Sid    = "PublishPipelineAlerts"
        Effect = "Allow"
        Action = [
          "sns:Publish",
        ]
        Resource = local.sns_topic_arn
      },
    ]
  })
}

resource "aws_iam_role" "eventbridge_sfn" {
  name = local.iam_role_eventbridge_sfn

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = "sts:AssumeRole"
        Principal = {
          Service = "events.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = local.iam_role_eventbridge_sfn
  }
}

resource "aws_iam_role_policy" "eventbridge_start_sfn" {
  name = "${local.name_prefix}-eventbridge-start-sfn"
  role = aws_iam_role.eventbridge_sfn.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "StartMonthlyPipeline"
        Effect = "Allow"
        Action = [
          "states:StartExecution",
        ]
        Resource = aws_sfn_state_machine.monthly_pipeline.arn
      },
    ]
  })
}
