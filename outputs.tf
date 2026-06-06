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

output "glue_job_parse_args_name" {
  description = "Nome do Glue Job Python Shell (S1-02)."
  value       = aws_glue_job.parse_args.name
}

output "glue_job_parse_args_arn" {
  description = "ARN do Glue Job Python Shell (S1-02)."
  value       = aws_glue_job.parse_args.arn
}

output "glue_script_parse_args_s3_uri" {
  description = "URI S3 do script parse_args_job.py."
  value       = "s3://${aws_s3_bucket.pipeline.id}/${local.glue_script_parse_args_key}"
}

output "sfn_monthly_pipeline_name" {
  description = "Nome da state machine Step Functions (S1-03)."
  value       = aws_sfn_state_machine.monthly_pipeline.name
}

output "sfn_monthly_pipeline_arn" {
  description = "ARN da state machine Step Functions (S1-03)."
  value       = aws_sfn_state_machine.monthly_pipeline.arn
}

output "sns_pipeline_alerts_arn" {
  description = "ARN do topico SNS de alertas de falha."
  value       = local.sns_topic_arn
}

output "eventbridge_monthly_pipeline_rule" {
  description = "Nome da regra EventBridge do agendamento mensal (null se create_eventbridge_schedule = false)."
  value       = var.create_eventbridge_schedule ? aws_cloudwatch_event_rule.monthly_pipeline[0].name : null
}

output "s3_input_day_csv_path" {
  description = "Caminho S3 padrao passado ao Glue Job (raw/day.csv)."
  value       = local.s3_input_day_csv_path
}

output "glue_job_validate_day_csv_name" {
  description = "Nome do Glue Job de validacao de schema day.csv (S2-01)."
  value       = aws_glue_job.validate_day_csv.name
}

output "glue_job_validate_day_csv_arn" {
  description = "ARN do Glue Job de validacao de schema day.csv (S2-01)."
  value       = aws_glue_job.validate_day_csv.arn
}

output "features_parquet_uri_template" {
  description = "Template S3 das features Parquet particionadas por ref_date (S2-03)."
  value       = local.features_parquet_uri_template
}
