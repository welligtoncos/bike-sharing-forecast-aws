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
