# project-glue-3 — Pipeline B3 (Ibovespa)

Infraestrutura Terraform para o pipeline de dados e ML da B3, com armazenamento S3 e Glue Jobs Python Shell integrados ao Step Functions.

## Status

| Story | Entrega | Status |
|-------|---------|--------|
| S1-01 | Bucket S3 + pastas + IAM Glue | ✅ |
| S1-02 | Glue Job Python Shell (`--ref_date`, `--s3_input_path`) | ✅ |

## Arquitetura em uma linha

```
Step Functions → Glue Job (Python Shell) → S3 (raw/ features/ predictions/ models/)
                      ↓
               CloudWatch Logs
```

## Início rápido

```powershell
# 1. Verificar credenciais AWS
aws sts get-caller-identity

# 2. Configurar variáveis
Copy-Item terraform.tfvars.example terraform.tfvars
# Edite aws_account_id com o Account da saída acima

# 3. Provisionar
terraform init
terraform apply -var-file="terraform.tfvars"

# 4. Executar o Glue Job de teste
$JOB = terraform output -raw glue_job_parse_args_name
$BUCKET = terraform output -raw s3_bucket_name
aws glue start-job-run --job-name $JOB --arguments "{`"--ref_date`":`"2024-06-01`",`"--s3_input_path`":`"s3://$BUCKET/raw/ibovespa.csv`"}"
```

## Documentação

| Documento | Conteúdo |
|-----------|----------|
| [Getting Started](docs/getting-started.md) | Pré-requisitos, deploy, validação |
| [Arquitetura](docs/architecture.md) | Fluxo de dados, recursos AWS, IAM |
| [S1-01 — Bucket S3](docs/s1-01-s3-bucket.md) | Estrutura de pastas e versionamento |
| [S1-02 — Glue Job](docs/s1-02-glue-job.md) | Argumentos, execução, Step Functions, logs |

## Estrutura do repositório

```
project-glue-3/
├── main.tf              # S3 bucket, versionamento, pastas
├── iam.tf               # Role Glue + policies S3/Catalog/Logs
├── glue.tf              # Glue Job Python Shell + upload do script
├── locals.tf            # Nomenclatura e constantes
├── variables.tf         # Variáveis de entrada
├── outputs.tf           # Valores exportados pós-apply
├── scripts/
│   └── parse_args_job.py   # Script do Glue Job (S1-02)
└── docs/                # Documentação detalhada
```

## Outputs principais

```powershell
terraform output s3_bucket_name          # bucket pipeline
terraform output glue_job_parse_args_name # nome do job
terraform output glue_role_arn             # role para novos jobs Glue
```
