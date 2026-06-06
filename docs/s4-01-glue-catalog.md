# S4-01 — Glue Catalog e Lake Formation

Registro da tabela `bike_sharing.predictions` no Glue Data Catalog, com schema inferido do Parquet e partição Hive `ref_date`.

## Objetivo

Permitir consulta SQL (Athena) sobre as predições do pipeline, com particionamento mensal por `ref_date`.

## Layout S3 (Hive)

```
s3://{bucket}/predictions/
└── ref_date=2011-06-01/
    └── predictions.parquet
```

Colunas do Parquet:

| Coluna | Tipo Glue | Descrição |
|--------|-----------|-----------|
| `dteday` | string | Data do registro |
| `cnt_real` | bigint | Demanda real |
| `cnt_pred` | double | Predição do modelo |

A coluna de partição `ref_date` **não** está no arquivo — é metadado registrado no Catalog.

## Pré-requisitos

1. `features/{ref_date}/features.parquet` (job `validate-day-csv`)
2. `predictions/ref_date={ref_date}/predictions.parquet` no S3

Enquanto o job de inferência real não existir, gere um Parquet de amostra:

```powershell
python scripts/generate_sample_predictions.py `
  --s3_input_path s3://glue-b3-dev-s3-pipeline-303238378103/raw/day.csv `
  --ref_date 2011-06-01
```

## Glue Job

| Item | Valor |
|------|-------|
| Nome | `glue-b3-dev-glue-job-register-predictions-catalog` |
| Script | `scripts/register_predictions_catalog_job.py` |
| Módulo | `scripts/glue_catalog_predictions.py` |

### Argumentos

| Argumento | Descrição |
|-----------|-----------|
| `--s3_input_path` | URI do `raw/day.csv` (deriva bucket) |
| `--ref_date` | Partição `ref_date` (YYYY-MM-DD) |
| `--database_name` | Default: `bike_sharing` |
| `--predictions_parquet_path` | Opcional — override do URI do Parquet |

### Executar

```powershell
aws glue start-job-run `
  --job-name glue-b3-dev-glue-job-register-predictions-catalog `
  --arguments '{"--ref_date":"2011-06-01","--s3_input_path":"s3://BUCKET/raw/day.csv","--database_name":"bike_sharing"}'
```

### Validar

```powershell
aws glue get-table --database-name bike_sharing --name predictions
aws glue get-partition `
  --database-name bike_sharing `
  --table-name predictions `
  --partition-values "2011-06-01"
```

## Terraform

| Recurso | Arquivo |
|---------|---------|
| Database `bike_sharing` | `glue_catalog.tf` |
| Glue Job register catalog | `glue_catalog.tf` |
| IAM escrita Catalog | `iam.tf` → `glue_catalog_write` |
| Lake Formation (opcional) | `enable_lake_formation = true` |

## Critérios de aceite

- Tabela `bike_sharing.predictions` criada no Glue Catalog
- Schema com `dteday`, `cnt_real`, `cnt_pred`
- Partição `ref_date` apontando para `s3://…/predictions/ref_date={ref_date}/`
- Consultável no Athena (ver [S4-02](s4-02-athena-query.md))

## Ver também

- [S4-02 — Query Athena](s4-02-athena-query.md)
- [Arquitetura](architecture.md)
