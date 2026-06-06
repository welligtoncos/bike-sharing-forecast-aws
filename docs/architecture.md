# Arquitetura

Visão geral da infraestrutura e do fluxo de dados do pipeline.

## Diagrama end-to-end

```mermaid
flowchart TB
    subgraph AGENDAMENTO["Agendamento · S1-03 ✅"]
        EB[EventBridge<br/>cron dia 1 / mês]
    end

    subgraph ORQUESTRACAO["Orquestração ✅"]
        SF1[monthly_pipeline<br/>S1-03]
        SF2[validate_predictions<br/>S4-02]
        SNS[SNS alertas falha]
    end

    subgraph COMPUTE["Glue Python Shell"]
        GJ1[parse_args<br/>S1-02 ✅]
        GJ2[validate_day_csv<br/>S2 ✅]
        GJ3[train_xgboost<br/>S3-01 ✅]
        GJ4[register_catalog<br/>S4-01 ✅]
    end

    subgraph S3["S3 pipeline · S1-01 ✅"]
        RAW[raw/day.csv]
        FEAT[features/…/features.parquet]
        MET[metrics/…/metrics.json]
        PRED["predictions/ref_date=…/"]
        ATHOUT[athena-results/]
        MOD[models/ · futuro]
    end

    subgraph ANALYTICS["Consulta · S4 ✅"]
        GC["Glue Catalog<br/>bike_sharing.predictions"]
        ATH[Athena workgroup]
        USR[Analista / BI]
    end

    EB --> SF1
    SF1 --> GJ1
    SF1 -.-> SNS

    RAW --> GJ2 --> FEAT
    FEAT --> GJ3 --> MET
    FEAT --> PRED
    PRED --> GJ4 --> GC

    SF2 --> ATH
    GC --> ATH
    PRED --> ATH
    ATH --> ATHOUT
    ATH --> USR

    classDef done fill:#d4edda,stroke:#28a745,color:#155724
    classDef future fill:#fff3cd,stroke:#ffc107,color:#856404
    class EB,SF1,SF2,GJ1,GJ2,GJ3,GJ4,RAW,FEAT,MET,PRED,GC,ATH,ATHOUT,SNS done
    class MOD future
```

## Pipeline de features (Sprint 2)

```mermaid
flowchart LR
    IN["raw/day.csv"] --> V["S2-01 validate_schema"]
    V --> F["S2-02 filter_by_ref_date"]
    F --> S["select_feature_columns"]
    S --> OUT["S2-03 features.parquet"]

    style IN fill:#d4edda
    style V fill:#d4edda
    style F fill:#d4edda
    style S fill:#d4edda
    style OUT fill:#d4edda
```

## Pipeline de ML e métricas (Sprint 3)

```mermaid
flowchart LR
    FEAT["features.parquet"] --> X["split 80/20"]
    X --> TR["XGBRegressor"]
    TR --> M["metrics.json<br/>RMSE + MAE"]

    style FEAT fill:#d4edda
    style X fill:#d4edda
    style TR fill:#d4edda
    style M fill:#d4edda
```

## Catalog + Athena (Sprint 4)

```mermaid
flowchart LR
    P["predictions.parquet"] --> REG["S4-01 boto3<br/>Glue Catalog"]
    REG --> T["bike_sharing.predictions<br/>partição ref_date"]
    T --> Q["S4-02 Athena SQL<br/>abs_error"]
    SF["Step Functions"] --> Q

    style P fill:#d4edda
    style REG fill:#d4edda
    style T fill:#d4edda
    style Q fill:#d4edda
    style SF fill:#d4edda
```

| Passo | Story | Artefato |
|-------|-------|----------|
| Parquet predições | dev / futuro inferência | `predictions/ref_date={ref_date}/predictions.parquet` |
| Registro Catalog | S4-01 | Tabela + partição Hive |
| Query analista | S4-02 | SQL com `abs_error`, ORDER BY `dteday` |
| Orquestração query | S4-02 | `sfn-validate-predictions` + `$.ref_date` |

## Fluxo de dados no S3

```
1. CSV bruto      → s3://{bucket}/raw/day.csv
2. Features       → s3://{bucket}/features/{ref_date}/features.parquet        ✅ S2-03
3. Métricas       → s3://{bucket}/metrics/{ref_date}/metrics.json              ✅ S3-01
4. Predições      → s3://{bucket}/predictions/ref_date={ref_date}/predictions.parquet  ✅ S3-03
5. Resultados SQL → s3://{bucket}/athena-results/                              ✅ S4-02
6. Modelo         → s3://{bucket}/models/{ref_date}/model.pkl                  ✅ S3-02
```

## Recursos AWS

| Recurso | Terraform | Nome (dev) |
|---------|-----------|------------|
| S3 Bucket | `aws_s3_bucket.pipeline` | `glue-b3-dev-s3-pipeline-{account}` |
| Glue Job parse_args | `aws_glue_job.parse_args` | `glue-b3-dev-glue-job-parse-args` |
| Glue Job features | `aws_glue_job.validate_day_csv` | `glue-b3-dev-glue-job-validate-day-csv` |
| Glue Job treino | `aws_glue_job.train_xgboost` | `glue-b3-dev-glue-job-train-xgboost` |
| Glue Job inferencia | `aws_glue_job.predict_xgboost` | `glue-b3-dev-glue-job-predict-xgboost` |
| Glue Job catalog | `aws_glue_job.register_predictions_catalog` | `glue-b3-dev-glue-job-register-predictions-catalog` |
| Glue Database | `aws_glue_catalog_database.bike_sharing` | `bike_sharing` |
| Athena Workgroup | `aws_athena_workgroup.pipeline` | `glue-b3-dev-athena-pipeline` |
| SFN mensal | `aws_sfn_state_machine.monthly_pipeline` | `glue-b3-dev-sfn-monthly-pipeline` |
| SFN Athena | `aws_sfn_state_machine.validate_predictions` | `glue-b3-dev-sfn-validate-predictions` |
| IAM Role Glue | `aws_iam_role.glue` | `glue-b3-dev-iam-glue` |
| IAM Role SFN | `aws_iam_role.stepfunctions` | Glue + SNS + Athena |

Scripts S3: ver pasta `scripts/` — cada Glue Job tem entry point + módulo compartilhado.

## IAM — Glue

```mermaid
flowchart LR
    GLUE[glue.amazonaws.com] -->|AssumeRole| ROLE[glue-b3-dev-iam-glue]

    ROLE --> P1[AWSGlueServiceRole]
    ROLE --> P2[glue-s3]
    ROLE --> P3[glue-catalog read b3_raw]
    ROLE --> P4[glue-catalog-write bike_sharing]
    ROLE --> P5[glue-logs]
```

## IAM — Step Functions

| Policy | Finalidade |
|--------|------------|
| `sfn-glue-sns` | Glue Job mensal + alertas SNS |
| `sfn-athena` | Queries Athena, leitura `predictions/`, escrita `athena-results/`, Glue Catalog `bike_sharing` |

## Integração Step Functions

| State machine | Uso | Input |
|---------------|-----|-------|
| `monthly_pipeline` | S2→S3→inferência→catalog→Athena | `{"ref_date":"2011-06-01"}` (opcional; default = mês corrente) |
| `validate_predictions` | Query Athena parametrizada | `{"ref_date":"2011-06-01"}` |
| `train_with_observability` | Treino + inferência + rmse_threshold | `{"ref_date":"2011-06-01","rmse_threshold":500}` |

Ver [S1-03 — Step Functions](s1-03-step-functions.md), [Guia de testes](pipeline-testing-guide.md) e [S4-02](s4-02-athena-query.md).
