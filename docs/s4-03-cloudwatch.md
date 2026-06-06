# S4-03 — CloudWatch: logs, alarmes e dashboard

Observabilidade do pipeline com métricas customizadas, alarmes SNS e dashboard.

## Métricas customizadas

Namespace: `glue-b3/dev/Pipeline` (via `cloudwatch_pipeline_namespace` output)

| Métrica | Origem | Uso |
|---------|--------|-----|
| `RMSE` | Job `train-xgboost` | Qualidade do modelo |
| `MAE` | Job `train-xgboost` | Erro absoluto médio |
| `RMSEThresholdBreached` | Job quando RMSE > threshold | Alarme S4-03 |
| `GlueJobFailure` | Job em exceção | Alarme falha Glue |
| `GlueJobLogFailure` | Log filter traceback | Alarme falha Glue |

## Alarmes (SNS)

| Alarme | Condição | Notificação |
|--------|----------|-------------|
| `glue-b3-dev-alarm-glue-job-failure` | `GlueJobFailure` ou traceback no log ≥ 1 | SNS pipeline alerts |
| `glue-b3-dev-alarm-rmse-threshold` | `RMSEThresholdBreached` Sum ≥ 1 | SNS pipeline alerts |

> Confirme inscrição e-mail no tópico SNS. CloudWatch precisa permissão `SNS:Publish` no tópico.

> **IAM limitada (`usuario-dados`):** no `terraform.tfvars`:
>
> ```hcl
> create_cloudwatch_log_metric_filter = false
> create_cloudwatch_alarms            = false
> create_cloudwatch_dashboard         = false
> ```
>
> Falhas Glue → métrica `GlueJobFailure` no job. Crie alarmes **uma vez** via CLI abaixo (não exige `ListTagsForResource` no operador).

### Criar alarmes via CLI (conta IAM limitada)

```powershell
$SNS = terraform output -raw sns_pipeline_alerts_arn
$NS   = "glue-b3/dev/Pipeline"

aws cloudwatch put-metric-alarm `
  --alarm-name glue-b3-dev-alarm-glue-job-failure `
  --alarm-description "Glue Job falhou" `
  --metric-name GlueJobFailure `
  --namespace $NS `
  --statistic Sum `
  --period 300 `
  --evaluation-periods 1 `
  --threshold 1 `
  --comparison-operator GreaterThanOrEqualToThreshold `
  --treat-missing-data notBreaching `
  --alarm-actions $SNS `
  --ok-actions $SNS

aws cloudwatch put-metric-alarm `
  --alarm-name glue-b3-dev-alarm-rmse-threshold `
  --alarm-description "RMSE excedeu threshold" `
  --metric-name RMSEThresholdBreached `
  --namespace $NS `
  --statistic Sum `
  --period 300 `
  --evaluation-periods 1 `
  --threshold 1 `
  --comparison-operator GreaterThanOrEqualToThreshold `
  --treat-missing-data notBreaching `
  --alarm-actions $SNS `
  --ok-actions $SNS
```

## Dashboard

Com `create_cloudwatch_dashboard = false` (padrão para IAM limitada), monte o dashboard manualmente no console CloudWatch ou peça permissão `cloudwatch:PutDashboard` a um admin.

Nome sugerido: `glue-b3-dev-pipeline-dashboard`

Widgets recomendados:
- RMSE e MAE (namespace `glue-b3/dev/Pipeline`, stat Maximum)
- RMSEThresholdBreached e GlueJobFailure (stat Sum)
- Widget de alarmes referenciando `glue-b3-dev-alarm-glue-job-failure` e `glue-b3-dev-alarm-rmse-threshold`

## Step Functions — threshold parametrizável

State machine: `glue-b3-dev-sfn-train-with-observability`

```powershell
$SFN = terraform output -raw sfn_train_with_observability_arn

aws stepfunctions start-execution `
  --state-machine-arn $SFN `
  --input '{"ref_date":"2011-06-01","rmse_threshold":500}'
```

| Input | Descrição |
|-------|-----------|
| `ref_date` | Partição mensal (YYYY-MM-DD) |
| `rmse_threshold` | RMSE máximo; se RMSE > threshold → métrica `RMSEThresholdBreached` → alarme |

Default Terraform: `rmse_threshold = 700` (variável `rmse_threshold`).

## Glue Job manual

```powershell
aws glue start-job-run `
  --job-name glue-b3-dev-glue-job-train-xgboost `
  --arguments '{"--ref_date":"2011-06-01","--s3_input_path":"s3://BUCKET/raw/day.csv","--rmse_threshold":"500","--cloudwatch_namespace":"glue-b3/dev/Pipeline"}'
```

## Validar alarme RMSE

1. Execute treino com threshold **abaixo** do RMSE real (ex.: `500` — RMSE ~629)
2. CloudWatch → Alarms → `alarm-rmse-threshold` → estado `ALARM`
3. E-mail SNS (se inscrito)

## Validar alarme falha Glue

1. Execute job com argumentos inválidos ou `ref_date` sem features
2. Verifique alarme `alarm-glue-job-failure` ou métrica `GlueJobFailure`

## Ver também

- [Arquitetura](architecture.md)
- [S4-02 — Athena](s4-02-athena-query.md)
