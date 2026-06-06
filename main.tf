# =============================================================================
# S1-01 — Bucket S3 do pipeline de ML
# =============================================================================
#
# Provisiona a camada de armazenamento base do pipeline Ibovespa:
#
#   s3://{bucket}/
#   ├── raw/          CSV bruto (entrada do pipeline)
#   ├── features/     datasets de feature engineering
#   ├── predictions/  saida do modelo (scores, previsoes)
#   └── models/       artefatos serializados (pickle, joblib, etc.)
#
# Criterios de aceite:
#   - Bucket com 4 pastas (prefixos S3)
#   - Versionamento habilitado
#   - Bloqueio de acesso publico
#   - Idempotente (terraform apply pode ser re-executado sem erro)
#
# Comandos:
#   terraform init
#   terraform plan  -var-file="terraform.tfvars"
#   terraform apply -var-file="terraform.tfvars"
# =============================================================================

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  # Tags aplicadas automaticamente a todos os recursos deste modulo.
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Provider sem default_tags — SNS/EventBridge nesta conta nao tem permissao sns:TagResource.
provider "aws" {
  alias  = "no_default_tags"
  region = var.aws_region
}

# Bucket unico do pipeline. Nome global: {project}-{env}-s3-pipeline-{account_id}
# force_destroy = true permite destroy mesmo com objetos (util em dev).
resource "aws_s3_bucket" "pipeline" {
  bucket        = local.s3_bucket_name
  force_destroy = true

  tags = {
    Name = local.s3_bucket_name
  }
}

# Versionamento obrigatorio (S1-01): protege contra sobrescrita acidental de CSVs e modelos.
resource "aws_s3_bucket_versioning" "pipeline" {
  bucket = aws_s3_bucket.pipeline.id

  versioning_configuration {
    status = "Enabled"
  }
}

# S3 nao tem pastas reais — sao prefixos de chave. Bloqueia qualquer acesso publico.
resource "aws_s3_bucket_public_access_block" "pipeline" {
  bucket = aws_s3_bucket.pipeline.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Cria os prefixos vazios para que aparecam no console S3 e em `aws s3 ls`.
# Objetos com content = "" sao placeholders; dados reais vao em raw/*.csv, etc.
resource "aws_s3_object" "folders" {
  for_each = local.s3_folders

  bucket  = aws_s3_bucket.pipeline.id
  key     = each.value
  content = ""
}
