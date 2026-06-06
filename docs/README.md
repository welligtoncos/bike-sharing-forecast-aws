# Documentação — project-glue-3

Índice da documentação do pipeline Bike Sharing / B3.

## Visão geral

| Documento | Descrição |
|-----------|-----------|
| [Getting Started](getting-started.md) | Configurar, aplicar Terraform e validar o pipeline |
| [Arquitetura](architecture.md) | Componentes, fluxo S1–S4, IAM, S3 |
| [**Guia de testes da esteira**](pipeline-testing-guide.md) | Onboarding de devs: pytest, S2→S4, checklist, troubleshooting |
| [**Casos de uso comerciais**](commercial-use-cases.md) | Cenários de negócio, adaptação e proposta de valor |

## Sprint 1 — Infraestrutura

| Documento | Descrição |
|-----------|-----------|
| [S1-01 — Bucket S3](s1-01-s3-bucket.md) | Pastas, versionamento, IAM S3 |
| [S1-02 — Glue Job](s1-02-glue-job.md) | Python Shell, argumentos, logs |
| [S1-03 — Step Functions](s1-03-step-functions.md) | Agendamento mensal, ASL, SNS, EventBridge |

## Sprint 4 — Catalog e Athena

| Documento | Descrição |
|-----------|-----------|
| [S4-01 — Glue Catalog](s4-01-glue-catalog.md) | Tabela `bike_sharing.predictions`, partição `ref_date` |
| [S4-02 — Query Athena](s4-02-athena-query.md) | SQL `abs_error`, Step Functions parametrizável |
| [S4-03 — CloudWatch](s4-03-cloudwatch.md) | Alarmes, dashboard, RMSE threshold via SFN |

> Sprints 2 (features) e 3 (treino XGBoost) estão documentados no [README](../README.md) e cobertos por testes em `tests/`.

## Convenção de nomenclatura

```
{project_name}-{environment}-{aws_service}-{purpose}[-{account_id}]
```

Exemplo (dev, conta `303238378103`):

| Recurso | Nome |
|---------|------|
| Bucket S3 | `glue-b3-dev-s3-pipeline-303238378103` |
| IAM Role Glue | `glue-b3-dev-iam-glue` |
| Glue Database | `bike_sharing` |
| Athena Workgroup | `glue-b3-dev-athena-pipeline` |

O `account_id` aparece apenas no nome do bucket (unicidade global na AWS).
