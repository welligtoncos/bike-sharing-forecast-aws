# Documentação — project-glue-3

Índice da documentação do pipeline B3.

| Documento | Descrição |
|-----------|-----------|
| [Getting Started](getting-started.md) | Como configurar, aplicar e validar a infraestrutura |
| [Arquitetura](architecture.md) | Visão geral dos componentes e fluxo de dados |
| [S1-01 — Bucket S3](s1-01-s3-bucket.md) | Bucket pipeline, pastas, versionamento, IAM S3 |
| [S1-02 — Glue Job](s1-02-glue-job.md) | Python Shell, argumentos, execução e integração Step Functions |

## Convenção de nomenclatura

```
{project_name}-{environment}-{aws_service}-{purpose}[-{account_id}]
```

Exemplo (dev, conta `303238378103`):

| Recurso | Nome |
|---------|------|
| Bucket S3 | `glue-b3-dev-s3-pipeline-303238378103` |
| IAM Role Glue | `glue-b3-dev-iam-glue` |
| Glue Job | `glue-b3-dev-glue-job-parse-args` |

O `account_id` aparece apenas no nome do bucket (unicidade global na AWS).
