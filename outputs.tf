# =============================================================================
# Outputs — use apos `terraform apply` para integrar scripts e proximas US
# =============================================================================
#
# Exemplos:
#   terraform output -raw s3_bucket_name
#   terraform output -raw glue_role_arn
#   terraform output s3_folders
# =============================================================================

output "name_prefix" {
  description = "Prefixo padrao de nomenclatura: {project}-{environment}."
  value       = local.name_prefix
}

output "s3_bucket_name" {
  description = "Nome do bucket S3 do pipeline (raw, features, predictions, models)."
  value       = aws_s3_bucket.pipeline.id
}

output "s3_bucket_arn" {
  description = "ARN do bucket S3 do pipeline."
  value       = aws_s3_bucket.pipeline.arn
}

output "s3_folders" {
  description = "Pastas (prefixos) criadas no bucket."
  value       = sort([for folder in local.s3_folders : "s3://${aws_s3_bucket.pipeline.id}/${folder}"])
}

output "glue_role_arn" {
  description = "ARN da IAM Role do Glue — use ao criar Glue Jobs/Crawlers."
  value       = aws_iam_role.glue.arn
}

output "glue_role_name" {
  description = "Nome da IAM Role do Glue."
  value       = aws_iam_role.glue.name
}
