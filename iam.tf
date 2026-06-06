# =============================================================================
# S1-01 — IAM para AWS Glue
# =============================================================================
#
# Role assumida por jobs/crawlers Glue para ler e gravar no bucket pipeline.
# Anexe esta role (glue_role_arn) ao criar Glue Jobs ou Crawlers nas proximas US.
#
# Permissoes:
#   - AWSGlueServiceRole (managed): operacoes padrao Glue
#   - Policy inline glue-s3: ListBucket + Get/Put/DeleteObject no bucket pipeline
#   - Policy inline glue-catalog: leitura Glue Data Catalog (S1-02)
#   - Policy inline glue-logs: CloudWatch Logs do Python Shell Job (S1-02)
# =============================================================================

# Trust policy: apenas o servico glue.amazonaws.com pode assumir esta role.
resource "aws_iam_role" "glue" {
  name = local.iam_role_glue

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = "sts:AssumeRole"
        Principal = {
          Service = "glue.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = local.iam_role_glue
  }
}

# Policy gerenciada pela AWS — cobre Glue Catalog, CloudWatch Logs e operacoes padrao.
resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

# Acesso minimo ao bucket deste modulo (least privilege por recurso).
resource "aws_iam_role_policy" "glue_s3" {
  name = "${local.name_prefix}-glue-s3"
  role = aws_iam_role.glue.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ListPipelineBucket"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
        ]
        Resource = aws_s3_bucket.pipeline.arn
      },
      {
        Sid    = "ReadWritePipelineObjects"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
        ]
        Resource = "${aws_s3_bucket.pipeline.arn}/*"
      },
    ]
  })
}

# Leitura do Glue Data Catalog — database legado b3_raw.
resource "aws_iam_role_policy" "glue_catalog" {
  name = "${local.name_prefix}-glue-catalog"
  role = aws_iam_role.glue.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadGlueCatalog"
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetDatabases",
          "glue:GetTable",
          "glue:GetTables",
          "glue:GetPartition",
          "glue:GetPartitions",
        ]
        Resource = concat(
          [local.glue_catalog_arn, local.glue_database_arn],
          local.glue_table_arns,
        )
      },
    ]
  })
}

# Escrita Glue Catalog — S4-01 database bike_sharing + tabela predictions.
resource "aws_iam_role_policy" "glue_catalog_write" {
  name = "${local.name_prefix}-glue-catalog-write"
  role = aws_iam_role.glue.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "WritePredictionsGlueCatalog"
        Effect = "Allow"
        Action = [
          "glue:CreateDatabase",
          "glue:UpdateDatabase",
          "glue:GetDatabase",
          "glue:CreateTable",
          "glue:UpdateTable",
          "glue:GetTable",
          "glue:CreatePartition",
          "glue:UpdatePartition",
          "glue:BatchCreatePartition",
          "glue:GetPartition",
          "glue:GetPartitions",
        ]
        Resource = concat(
          [local.glue_catalog_arn, local.glue_predictions_database_arn],
          local.glue_predictions_table_arns,
        )
      },
    ]
  })
}

# Logs do Glue Python Shell Job em /aws-glue/python-jobs (continuous logging).
resource "aws_iam_role_policy" "glue_cloudwatch_metrics" {
  name = "${local.name_prefix}-glue-cloudwatch-metrics"
  role = aws_iam_role.glue.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "PublishPipelineMetrics"
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = local.cloudwatch_pipeline_namespace
          }
        }
      },
    ]
  })
}

resource "aws_iam_role_policy" "glue_logs" {
  name = "${local.name_prefix}-glue-logs"
  role = aws_iam_role.glue.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "WriteGlueJobLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = [
          local.glue_job_log_group_arn,
          local.glue_job_log_group_stream_arn,
        ]
      },
    ]
  })
}
