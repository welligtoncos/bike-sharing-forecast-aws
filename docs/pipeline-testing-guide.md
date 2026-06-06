# Guia de testes da esteira — para desenvolvedores

Este documento descreve **como outro desenvolvedor** configura o ambiente, executa a esteira de ponta a ponta e valida cada etapa (S2 → S4 + observabilidade S4-03).

> **Pipeline mensal:** `monthly_pipeline` encadeia S2 → treino → inferência → catalog → Athena. Para testes com dataset 2011–2012, passe `{"ref_date":"2011-06-01"}` no input da execução.

## Pré-requisitos

| Item | Verificação |
|------|-------------|
| Terraform ≥ 1.5 | `terraform version` |
| AWS CLI v2 | `aws --version` |
| Python 3.10+ | `python --version` |
| Credenciais AWS | `aws sts get-caller-identity` |
| Repositório clonado | `git clone …` + `cd project-glue-3` |

### Dataset de teste

O projeto usa **Bike Sharing (2011–2012)**. Para testes manuais, use sempre um `ref_date` dentro desse intervalo:

```
ref_date = 2011-06-01
```

O arquivo `raw/day.csv` deve existir no bucket após o `terraform apply` (ou upload manual).

### Permissões IAM do operador

| Ação típica | Permissões necessárias |
|-------------|------------------------|
| `terraform apply` | S3, IAM, Glue, Step Functions (ver [Getting Started](getting-started.md)) |
| Disparar Glue jobs | `glue:StartJobRun`, `glue:GetJobRun` |
| Disparar Step Functions | `states:StartExecution`, `states:DescribeExecution` |
| Consultar Athena | `athena:StartQueryExecution` ou console Athena |
| CloudWatch (opcional) | `cloudwatch:GetMetricStatistics`, `cloudwatch:DescribeAlarms` |

> Contas com IAM limitada (ex.: sem `logs:PutMetricFilter`, `cloudwatch:PutDashboard`): mantenha no `terraform.tfvars` as flags `create_cloudwatch_* = false`. Ver [S4-03 — CloudWatch](s4-03-cloudwatch.md).

---

## Fase 0 — Setup inicial (uma vez por dev/conta)

```powershell
cd c:\welligton-aws\project-glue-3

# 1. Credenciais
aws sts get-caller-identity

# 2. Variáveis Terraform
Copy-Item terraform.tfvars.example terraform.tfvars
# Edite aws_account_id e sns_pipeline_alerts_arn se necessário

# 3. Infraestrutura
terraform init
terraform apply -var-file="terraform.tfvars"

# 4. Dependências de teste local
pip install -r requirements-dev.txt
```

**Critério de sucesso:** `Apply complete!` e `terraform plan` retorna `No changes`.

---

## Fase 1 — Testes locais (sem AWS)

Rode antes de qualquer deploy ou após alterar scripts Python:

```powershell
python -m pytest tests/ -v
```

| Módulo de teste | O que cobre |
|-----------------|-------------|
| `test_schema_validation.py` | Validação S2 (schema, filtro por mês) |
| `test_xgboost_training.py` | Treino S3 (split, métricas) |
| `test_glue_catalog_predictions.py` | Registro S4-01 |
| `test_pipeline_observability.py` | Métricas CloudWatch S4-03 |
| `test_athena_predictions_query.py` | SQL S4-02 |

**Critério de sucesso:** todos os testes passam (0 failures).

---

## Fase 2 — Smoke test: pipeline mensal completo (SFN)

```powershell
$SFN = terraform output -raw sfn_monthly_pipeline_arn

# Use ref_date do dataset Bike Sharing (2011–2012)
$exec = aws stepfunctions start-execution `
  --state-machine-arn $SFN `
  --name "e2e-$(Get-Date -Format 'yyyyMMdd-HHmmss')" `
  --input '{"ref_date":"2011-06-01"}' `
  --query executionArn --output text

do {
  Start-Sleep -Seconds 15
  $status = aws stepfunctions describe-execution --execution-arn $exec --query status --output text
  Write-Host "SFN status: $status"
} while ($status -eq "RUNNING")

aws stepfunctions describe-execution --execution-arn $exec
```

**Critério de sucesso:** `status: SUCCEEDED` (5 Glue jobs + Athena; ~10–20 min).

Alternativa smoke S1 isolado: job `parse_args` manualmente ([S1-02](s1-02-glue-job.md)).

---

## Fase 3 — Esteira completa S2 → S4 (validação principal)

Esta é a **prova de funcionamento** que todo dev deve executar ao onboarding ou após mudanças nos jobs.

### Variáveis

```powershell
$BUCKET = terraform output -raw s3_bucket_name
$ref    = "2011-06-01"
$raw    = "s3://$BUCKET/raw/day.csv"
```

### Helper — aguardar Glue job

```powershell
function Wait-GlueJob {
  param([string]$JobName, [string]$RunId)
  do {
    Start-Sleep -Seconds 15
    $state = aws glue get-job-run --job-name $JobName --run-id $RunId `
      --query JobRun.JobRunState --output text
    Write-Host "$JobName → $state"
  } while ($state -in @("RUNNING", "STARTING", "STOPPING"))
  if ($state -ne "SUCCEEDED") {
    aws glue get-job-run --job-name $JobName --run-id $RunId `
      --query "JobRun.{State:JobRunState,Error:ErrorMessage}" --output json
    throw "Job $JobName falhou: $state"
  }
}
```

> Jobs Glue **Python Shell** executam **um run por vez**. Não dispare dois runs do mesmo job em paralelo.

### Passo 1 — S2: ingestão e features

```powershell
$runS2 = aws glue start-job-run `
  --job-name glue-b3-dev-glue-job-validate-day-csv `
  --arguments "{`"--ref_date`":`"$ref`",`"--s3_input_path`":`"$raw`"}" `
  --query JobRunId --output text

Wait-GlueJob -JobName glue-b3-dev-glue-job-validate-day-csv -RunId $runS2
aws s3 ls "s3://$BUCKET/features/$ref/"
```

| Verificação | Esperado |
|-------------|----------|
| Arquivo S3 | `features/2011-06-01/features.parquet` existe |
| Log Glue | Sem `Traceback`; mensagem de schema OK |

### Passo 2 — S3: treino e métricas

```powershell
$runS3 = aws glue start-job-run `
  --job-name glue-b3-dev-glue-job-train-xgboost `
  --arguments "{`"--ref_date`":`"$ref`",`"--s3_input_path`":`"$raw`"}" `
  --query JobRunId --output text

Wait-GlueJob -JobName glue-b3-dev-glue-job-train-xgboost -RunId $runS3
aws s3 cp "s3://$BUCKET/metrics/$ref/metrics.json" -
```

| Verificação | Esperado |
|-------------|----------|
| `JobRunState` | `SUCCEEDED` |
| `metrics.json` | Campos `rmse`, `mae`, `"random_state": 42`, `"test_size": 0.2` |
| RMSE típico | ~600–650 para `2011-06-01` (varia levemente) |

### Passo 3 — S3-03: inferência (predições)

```powershell
$runPred = aws glue start-job-run `
  --job-name glue-b3-dev-glue-job-predict-xgboost `
  --arguments "{`"--ref_date`":`"$ref`",`"--s3_input_path`":`"$raw`"}" `
  --query JobRunId --output text

Wait-GlueJob -JobName glue-b3-dev-glue-job-predict-xgboost -RunId $runPred
aws s3 ls "s3://$BUCKET/models/$ref/"
aws s3 ls "s3://$BUCKET/predictions/ref_date=$ref/"
```

| Verificação | Esperado |
|-------------|----------|
| `model.pkl` | `models/2011-06-01/model.pkl` (S3-02) |
| Parquet | `predictions/ref_date=2011-06-01/predictions.parquet` |
| Schema | `dteday`, `cnt_real`, `cnt_pred`; `cnt_pred` ≥ 0 |

### Passo 4 — S4-01: Glue Catalog

```powershell
$runS4 = aws glue start-job-run `
  --job-name glue-b3-dev-glue-job-register-predictions-catalog `
  --arguments "{`"--ref_date`":`"$ref`",`"--s3_input_path`":`"$raw`",`"--database_name`":`"bike_sharing`"}" `
  --query JobRunId --output text

Wait-GlueJob -JobName glue-b3-dev-glue-job-register-predictions-catalog -RunId $runS4

aws glue get-partitions `
  --database-name bike_sharing `
  --table-name predictions `
  --query "Partitions[?Values[0]=='$ref'].Values" --output table
```

| Verificação | Esperado |
|-------------|----------|
| Partição | `ref_date=2011-06-01` listada |
| Console Glue | Tabela `bike_sharing.predictions` visível |

### Passo 5 — S4-02: Athena via Step Functions

```powershell
$SFN = terraform output -raw sfn_validate_predictions_arn
$exec = aws stepfunctions start-execution `
  --state-machine-arn $SFN `
  --input "{`"ref_date`":`"$ref`"}" `
  --query executionArn --output text

do {
  Start-Sleep -Seconds 5
  $status = aws stepfunctions describe-execution --execution-arn $exec --query status --output text
} while ($status -eq "RUNNING")

aws stepfunctions describe-execution --execution-arn $exec
```

Query SQL equivalente (console Athena ou CLI):

```sql
SELECT dteday, cnt_real, cnt_pred, ABS(cnt_real - cnt_pred) AS abs_error
FROM bike_sharing.predictions
WHERE ref_date = '2011-06-01'
ORDER BY dteday ASC
LIMIT 10;
```

| Verificação | Esperado |
|-------------|----------|
| SFN | `SUCCEEDED` |
| Athena | ~30 linhas (dias de jun/2011), `abs_error` numérico |
| S3 | Resultado em `athena-results/` |

---

## Fase 4 — Observabilidade S4-03 (opcional)

Testa métricas CloudWatch, threshold parametrizável e alarmes.

```powershell
$SFN = terraform output -raw sfn_train_with_observability_arn
$exec = aws stepfunctions start-execution `
  --state-machine-arn $SFN `
  --input '{"ref_date":"2011-06-01","rmse_threshold":500}' `
  --query executionArn --output text

# Aguardar SUCCEEDED…

$NS = terraform output -raw cloudwatch_pipeline_namespace
$START = (Get-Date).AddHours(-2).ToUniversalTime().ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
$END   = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")

aws cloudwatch get-metric-statistics `
  --namespace $NS --metric-name RMSE `
  --dimensions Name=ref_date,Value=2011-06-01 `
  --start-time $START --end-time $END `
  --period 300 --statistics Maximum

aws cloudwatch describe-alarms `
  --alarm-names glue-b3-dev-alarm-rmse-threshold `
  --query "MetricAlarms[0].StateValue" --output text
```

| Cenário | `rmse_threshold` | Resultado esperado |
|---------|------------------|-------------------|
| Breach | `500` (abaixo do RMSE real) | Métrica `RMSEThresholdBreached` = 1; alarme → `ALARM` |
| OK | `900` (acima do RMSE real) | Sem breach; alarme → `OK` |

Detalhes e CLI de alarmes: [S4-03 — CloudWatch](s4-03-cloudwatch.md).

---

## Checklist de aceitação (PR / release)

Use esta lista antes de merge ou demo:

- [ ] `pytest tests/ -v` — 0 failures
- [ ] `terraform plan` — no changes (ou plano revisado)
- [ ] S2 → `features/{ref_date}/features.parquet` no S3
- [ ] S3 → `metrics/{ref_date}/metrics.json` com RMSE/MAE
- [ ] Predições → `predictions/ref_date={ref_date}/predictions.parquet`
- [ ] S4-01 → partição no Glue Catalog
- [ ] S4-02 → SFN `validate-predictions` SUCCEEDED + query Athena retorna dados
- [ ] (Opcional) S4-03 → métricas em `glue-b3/dev/Pipeline`

---

## Testes de regressão e cenários negativos

| Cenário | Como simular | Resultado esperado |
|---------|--------------|-------------------|
| Schema inválido | Corromper coluna em `day.csv` (dev only) | Job S2 `FAILED` |
| `ref_date` sem dados | `--ref_date 2099-01-01` | Job S2 ou S3 `FAILED` ou parquet vazio |
| Treino sem features | Pular passo S2 | Job S3 `FAILED` |
| Catalog sem parquet | Pular job predict | Job S4-01 falha ou partição vazia |
| Falha Glue + alarme | Args inválidos no train job | Métrica `GlueJobFailure`; alarme falha Glue |

Logs: CloudWatch → Log groups → `/aws-glue/python-jobs`.

---

## Troubleshooting

| Sintoma | Causa provável | Ação |
|---------|----------------|------|
| JSON inválido no `--arguments` | Escape `\"` no PowerShell | Use aspas simples ou `file://glue-args.json` |
| Job fica `RUNNING` forever | Outro run do mesmo job ativo | `aws glue get-job-runs --job-name …` e aguarde |
| Athena `TABLE_NOT_FOUND` | S4-01 não rodou ou DB errado | Confirme `bike_sharing.predictions` no console Glue |
| Métricas CloudWatch vazias | Job treino sem args observabilidade | Use SFN `train-with-observability` ou passe `--cloudwatch_namespace` |
| Terraform falha em alarmes | IAM limitada | `create_cloudwatch_alarms = false`; alarmes via CLI |
| RMSE diferente do esperado | Dados ou split alterados | Compare `metrics.json` e `"random_state": 42` |

---

## Referências

| Documento | Conteúdo |
|-----------|----------|
| [Getting Started](getting-started.md) | Setup Terraform e smoke S1 |
| [Arquitetura](architecture.md) | Diagrama e recursos AWS |
| [S4-02 — Athena](s4-02-athena-query.md) | SQL e workgroup |
| [S4-03 — CloudWatch](s4-03-cloudwatch.md) | Alarmes e métricas |
| [Casos de uso comerciais](commercial-use-cases.md) | Onde aplicar este padrão |
