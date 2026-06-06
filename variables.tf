# =============================================================================
# Variaveis de entrada — copie terraform.tfvars.example para terraform.tfvars
# =============================================================================
#
# aws_account_id: obtenha com `aws sts get-caller-identity --query Account --output text`
# Credenciais AWS: ~/.aws/credentials ou variaveis AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
# =============================================================================

variable "project_name" {
  description = "Nome do projeto utilizado na nomenclatura dos recursos."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "project_name deve conter apenas letras minusculas, numeros e hifens."
  }
}

variable "aws_account_id" {
  description = "ID da conta AWS utilizado na nomenclatura do bucket S3."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "aws_account_id deve ser um ID de conta AWS valido com 12 digitos."
  }
}

variable "aws_region" {
  description = "Regiao AWS onde os recursos serao provisionados."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Ambiente de deploy. Usado no prefixo de nomenclatura de todos os recursos."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "stg", "staging", "prod"], var.environment)
    error_message = "environment deve ser: dev, stg, staging ou prod."
  }
}

variable "glue_db_name" {
  description = "Nome logico do Glue Database (usado na policy IAM de acesso ao Catalog)."
  type        = string
  default     = "b3_raw"

  validation {
    condition     = can(regex("^[a-z0-9_]+$", var.glue_db_name))
    error_message = "glue_db_name deve conter apenas letras minusculas, numeros e underscores."
  }
}

variable "sns_pipeline_alerts_arn" {
  description = "ARN do topico SNS de alertas. Use topico pre-existente se o operador Terraform nao tem sns:ListTagsForResource."
  type        = string
  default     = ""
}

variable "create_sns_topic" {
  description = "Cria topico SNS via Terraform. Requer sns:CreateTopic e sns:ListTagsForResource."
  type        = bool
  default     = false
}

variable "pipeline_alert_email" {
  description = "E-mail para alertas SNS em falha do pipeline (requer confirmacao no inbox)."
  type        = string
  default     = ""
}

variable "create_eventbridge_schedule" {
  description = "Cria regra EventBridge mensal. Requer events:PutRule e events:PutTargets."
  type        = bool
  default     = true
}

variable "monthly_pipeline_schedule" {
  description = "Cron EventBridge: execucao mensal (padrao dia 1 as 06:00 UTC)."
  type        = string
  default     = "cron(0 6 1 * ? *)"
}

variable "monthly_pipeline_enabled" {
  description = "Habilita a regra EventBridge do pipeline mensal."
  type        = bool
  default     = true
}
