# S4-02 — Consulta Athena (validação de predições)

Query SQL para analistas validarem predições do mês: `dteday`, `cnt_real`, `cnt_pred` e erro absoluto.

## Query SQL

### Validação em duas consultas (modelo vs gabarito)

| Consulta | Coluna | Significado |
|----------|--------|-------------|
| **A — Modelo prevê** | `cnt_pred` | Predição do XGBoost |
| **B — Gabarito** | `cnt_real` | Valor real observado |

**A — O que o modelo prevê:**

```sql
SELECT dteday, cnt_pred AS alugueis_previstos
FROM bike_sharing.predictions
WHERE ref_date = '2011-06-01'
ORDER BY dteday ASC;
```

**B — Gabarito (valor real):**

```sql
SELECT dteday, cnt_real AS alugueis_reais
FROM bike_sharing.predictions
WHERE ref_date = '2011-06-01'
ORDER BY dteday ASC;
```

Detalhes para analistas: [Guia do usuário — dataset e modelo](guia-usuario-modelo.md).

### Query combinada (validação com erro absoluto)

```sql
SELECT
    dteday,
    cnt_real,
    cnt_pred,
    ABS(cnt_real - cnt_pred) AS abs_error
FROM bike_sharing.predictions
WHERE ref_date = '2011-06-01'
ORDER BY dteday ASC
```

Arquivo estático: [`athena/predictions_validation.sql`](../athena/predictions_validation.sql)

Builder Python (validação de `ref_date` anti-injeção SQL):

```python
from athena_predictions_query import build_predictions_validation_query

sql = build_predictions_validation_query("2011-06-01")
```

## Pré-requisitos

- Tabela `bike_sharing.predictions` registrada ([S4-01](s4-01-glue-catalog.md))
- Parquet em `predictions/ref_date={ref_date}/predictions.parquet`
- `terraform apply` com `athena.tf` (workgroup + Step Functions)

## Workgroup Athena

| Item | Valor |
|------|-------|
| Nome | `glue-b3-dev-athena-pipeline` |
| Resultados | `s3://{bucket}/athena-results/` |

```powershell
terraform output athena_workgroup_name
terraform output -raw athena_query_predictions_example
```

## Executar no console Athena

1. Athena → Query editor
2. Database: `bike_sharing`
3. Workgroup: `glue-b3-dev-athena-pipeline`
4. Cole a query SQL substituindo `ref_date`
5. Run query

## Executar via AWS CLI

```powershell
$bucket = terraform output -raw s3_bucket_name
$wg     = terraform output -raw athena_workgroup_name

aws athena start-query-execution `
  --work-group $wg `
  --query-execution-context Database=bike_sharing `
  --result-configuration "OutputLocation=s3://$bucket/athena-results/" `
  --query-string "SELECT dteday, cnt_real, cnt_pred, ABS(cnt_real - cnt_pred) AS abs_error FROM bike_sharing.predictions WHERE ref_date = '2011-06-01' ORDER BY dteday ASC"
```

## Step Functions (ref_date parametrizável)

State machine: `glue-b3-dev-sfn-validate-predictions`

Fluxo ASL (`stepfunctions/validate_predictions.asl.json.tpl`):

1. **BuildQuery** — monta SQL com `States.Format(..., $.ref_date)`
2. **RunAthenaQuery** — `athena:startQueryExecution.sync`

```powershell
$SFN = terraform output -raw sfn_validate_predictions_arn

aws stepfunctions start-execution `
  --state-machine-arn $SFN `
  --name "athena-$(Get-Date -Format 'yyyyMMdd-HHmmss')" `
  --input '{"ref_date":"2011-06-01"}'
```

Verifique status:

```powershell
aws stepfunctions describe-execution --execution-arn <arn>
```

## Critérios de aceite

| Critério | Como validar |
|----------|--------------|
| Query executa sem erro | Status `SUCCEEDED` no Athena ou Step Functions |
| 4 colunas | `dteday`, `cnt_real`, `cnt_pred`, `abs_error` |
| Ordenação ASC | Primeira linha = menor `dteday` do mês |
| Parametrizável | Step Functions input `{"ref_date":"YYYY-MM-DD"}` |

## Resultado esperado (exemplo)

| dteday | cnt_real | cnt_pred | abs_error |
|--------|----------|----------|-----------|
| 2011-06-01 | 2134 | 2100.5 | 33.5 |
| 2011-06-02 | 1918 | 1925.1 | 7.1 |
| … | … | … | … |

## Ver também

- [S4-01 — Glue Catalog](s4-01-glue-catalog.md)
- [Arquitetura](architecture.md)
