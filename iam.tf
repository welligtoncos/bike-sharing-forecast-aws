# =============================================================================
# S1-01 — IAM para AWS Glue
# =============================================================================
#
# Role assumida por jobs/crawlers Glue para ler e gravar no bucket pipeline.
# Anexe esta role (glue_role_arn) ao criar Glue Jobs ou Crawlers nas proximas US.
#
# Permissoes:
#   - AWSGlueServiceRole (managed): catalogo, logs basicos, operacoes Glue
#   - Policy inline glue-s3: ListBucket + Get/Put/DeleteObject no bucket pipeline
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
