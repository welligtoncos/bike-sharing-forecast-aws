# Getting Started

Guia para configurar o ambiente, executar o Terraform e validar o **Sprint 1** (S1-01 e S1-02).

## Pré-requisitos

| Ferramenta | Versão mínima | Verificação |
|------------|---------------|-------------|
| Terraform | 1.5 | `terraform version` |
| AWS CLI | v2 | `aws --version` |
| Sessão AWS | ativa | `aws sts get-caller-identity` |
| PowerShell | 5+ | Windows |

### Permissões IAM do operador

O usuário que executa `terraform apply` precisa de permissões para:

| Serviço | Ações principais |
|---------|------------------|
| S3 | `CreateBucket`, `PutObject`, `PutBucket*` |
| IAM | `CreateRole`, `PutRolePolicy`, `AttachRolePolicy` |
| Glue | `CreateJob`, `GetJob`, `StartJobRun` |
| Step Functions | `CreateStateMachine`, `StartExecution`, `DescribeExecution` |
| EventBridge | `PutRule`, `PutTargets` |
| SNS | `CreateTopic`, `Subscribe`, `Publish` |

> **Nota:** se `sns:ListTagsForResource` ou `events:TagResource` falhar, o provider `aws.no_default_tags` evita tags automáticas em SNS/EventBridge/SFN. Se `events:PutRule` falhar, solicite permissão ao administrador IAM.

> A **role Glue** (`glue-b3-dev-iam-glue`) recebe permissões próprias para S3, Catalog e CloudWatch Logs durante a execução do job — isso é independente das permissões do seu usuário IAM.

## Autenticação AWS

Credenciais ficam em `C:\Users\<usuario>\.aws\credentials` (perfis `default` ou `dev`).

```powershell
aws sts get-caller-identity
```

Saída esperada:

```json
{
    "Account": "303238378103",
    "Arn": "arn:aws:iam::303238378103:user/usuario-dados"
}
```

Para usar outro perfil:

```powershell
$env:AWS_PROFILE = "dev"
aws sts get-caller-identity
```

## Configuração

### Criar `terraform.tfvars`

```powershell
Copy-Item terraform.tfvars.example terraform.tfvars
```

Ou gere automaticamente:

```powershell
$ACCOUNT_ID = aws sts get-caller-identity --query Account --output text

@"
project_name   = "glue-b3"
aws_account_id = "$ACCOUNT_ID"
aws_region     = "us-east-1"
environment    = "dev"
glue_db_name   = "b3_raw"
"@ | Set-Content terraform.tfvars
```

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `project_name` | Prefixo do projeto | `glue-b3` |
| `aws_account_id` | ID da conta (12 dígitos) | `303238378103` |
| `aws_region` | Região dos recursos | `us-east-1` |
| `environment` | Ambiente | `dev` |
| `glue_db_name` | Database Glue referenciado na policy IAM | `b3_raw` |

> `terraform.tfvars` está no `.gitignore` — nunca commite valores locais.

## Deploy

```powershell
cd c:\welligton-aws\project-glue-3

terraform init
terraform plan  -var-file="terraform.tfvars"
terraform apply -var-file="terraform.tfvars"
```

**Esperado no final:** `Apply complete!` com outputs de bucket, role e job.

## Validação pós-deploy

### 1. Idempotência

```powershell
terraform plan -var-file="terraform.tfvars"
```

Esperado: `No changes. Your infrastructure matches the configuration.`

### 2. Bucket e pastas

```powershell
$BUCKET = terraform output -raw s3_bucket_name
aws s3 ls "s3://$BUCKET/"
```

Esperado:

```
features/
models/
predictions/
raw/
scripts/
```

### 3. Versionamento

```powershell
aws s3api get-bucket-versioning --bucket $BUCKET
```

Esperado: `"Status": "Enabled"`

### 4. Glue Job — execução manual

```powershell
$JOB = terraform output -raw glue_job_parse_args_name

# Criar arquivo de argumentos (evita problemas de escape no PowerShell)
@'
{"--ref_date":"2024-06-01","--s3_input_path":"s3://BUCKET/raw/ibovespa.csv"}
'@.Replace("BUCKET", $BUCKET) | Set-Content args.json -Encoding ascii

$RUN = aws glue start-job-run --job-name $JOB --arguments file://args.json --query JobRunId --output text
Write-Host "JobRunId: $RUN"

# Aguardar conclusão
do {
  Start-Sleep -Seconds 10
  $status = aws glue get-job-run --job-name $JOB --run-id $RUN --query JobRun.JobRunState --output text
  Write-Host "Status: $status"
} while ($status -in @("RUNNING", "STARTING"))

aws glue get-job-run --job-name $JOB --run-id $RUN --query "JobRun.{State:JobRunState,Error:ErrorMessage}" --output json
Remove-Item args.json
```

Esperado: `"State": "SUCCEEDED"`

### 5. Outputs

```powershell
terraform output
```

## Rollback

Para remover todos os recursos:

```powershell
terraform destroy -var-file="terraform.tfvars"
```

> O bucket tem `force_destroy = true` em dev, permitindo destroy mesmo com objetos.

## Próximos passos

- [Arquitetura](architecture.md) — entenda o fluxo completo
- [S1-02 — Glue Job](s1-02-glue-job.md) — integração com Step Functions
