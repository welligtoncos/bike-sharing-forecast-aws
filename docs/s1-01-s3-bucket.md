# S1-01 — Bucket S3 do Pipeline

**Story:** Como engenheiro, quero criar o bucket S3 e estrutura de pastas para armazenar o CSV e os resultados do modelo.

## Objetivo

Provisionar a camada de armazenamento base do pipeline de ML:

1. Bucket S3 único com pastas organizadas por estágio do pipeline
2. Versionamento habilitado
3. Acesso público bloqueado
4. IAM Role Glue com acesso ao bucket

## Estrutura de pastas

```
s3://glue-b3-dev-s3-pipeline-{account_id}/
├── raw/           ← CSV bruto (entrada)
├── features/      ← datasets pós feature engineering
├── predictions/   ← saída do modelo (scores, previsões)
├── models/        ← artefatos serializados (pickle, joblib)
└── scripts/       ← scripts Glue (S1-02)
```

> S3 não possui pastas reais — são **prefixos de chave**. Os placeholders vazios em `raw/`, `features/`, etc. existem para aparecer no console AWS.

## Recursos criados

| Recurso Terraform | Descrição |
|-------------------|-----------|
| `aws_s3_bucket.pipeline` | Bucket principal |
| `aws_s3_bucket_versioning.pipeline` | Versionamento Enabled |
| `aws_s3_bucket_public_access_block.pipeline` | Bloqueio público total |
| `aws_s3_object.folders` | Prefixos das 4 pastas |
| `aws_iam_role.glue` | Role para Glue Jobs |
| `aws_iam_role_policy.glue_s3` | Acesso S3 ao bucket |

## Propriedades do bucket

| Propriedade | Valor |
|-------------|-------|
| Nome | `{project}-{env}-s3-pipeline-{account_id}` |
| Versionamento | Enabled |
| `force_destroy` | `true` (dev) |
| Acesso público | bloqueado |

## Critérios de aceite

| Critério | Status |
|----------|--------|
| Bucket criado com 4 pastas | ✅ |
| Permissões IAM Glue configuradas | ✅ |
| Versionamento ativado | ✅ |
| Script idempotente (re-apply sem erro) | ✅ |

## Como usar

### Upload de CSV para raw/

```powershell
$BUCKET = terraform output -raw s3_bucket_name
aws s3 cp ibovespa_stocks.csv "s3://$BUCKET/raw/ibovespa_stocks.csv"
aws s3 ls "s3://$BUCKET/raw/"
```

### Listar versões de um objeto

```powershell
aws s3api list-object-versions --bucket $BUCKET --prefix raw/ibovespa_stocks.csv
```

### Consultar outputs

```powershell
terraform output s3_bucket_name
terraform output s3_bucket_arn
terraform output s3_folders
```

## Código Terraform

Arquivos envolvidos: `main.tf`, `iam.tf`, `locals.tf`

Nomenclatura centralizada em `locals.tf`:

```hcl
s3_bucket_name = "${local.name_prefix}-s3-pipeline-${local.global_suffix}"

s3_folders = toset([
  "raw/",
  "features/",
  "predictions/",
  "models/",
])
```

## Testes

Ver seção **Validação pós-deploy** em [Getting Started](getting-started.md).
