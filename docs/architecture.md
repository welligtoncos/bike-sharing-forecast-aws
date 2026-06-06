# Arquitetura

Visão geral da infraestrutura e do fluxo de dados do pipeline.

## Diagrama end-to-end

```mermaid
flowchart TB
    subgraph TRIGGER["Disparo"]
        EB["EventBridge Rule<br/>cron(0 6 1 * ? *)<br/>dia 1 · 06:00 UTC"]
        MANUAL["Execução manual<br/>aws stepfunctions start-execution<br/>input: ref_date opcional"]
    end

    subgraph SFN["Step Functions · monthly_pipeline"]
        direction TB
        S00["00 Escolher ref_date<br/>manual ou YYYY-MM-01 auto"]
        S01["01 Montar argumentos<br/>s3_input_path · database · Athena · threshold"]
        S02["Glue S2 validate-day-csv"]
        S03["Glue S3 train-xgboost"]
        S04["Glue S3 predict-xgboost"]
        S05["Glue S4 register-catalog"]
        S06["Prep SQL Athena"]
        S07["Athena validar predições"]
        FAIL["SNS alerta → Fail"]
        S00 --> S01 --> S02 --> S03 --> S04 --> S05 --> S06 --> S07
        S02 & S03 & S04 & S05 & S07 -.->|erro| FAIL
    end

    subgraph GLUE["AWS Glue · Python Shell"]
        GJ2["validate_day_csv_job.py<br/>S2 schema + filtro mês"]
        GJ3["train_xgboost_job.py<br/>S3 treino + métricas"]
        GJ4["predict_xgboost_job.py<br/>S3-03 inferência"]
        GJ5["register_predictions_catalog_job.py<br/>S4-01 Catalog"]
    end

    subgraph STORAGE["Amazon S3 · pipeline bucket"]
        RAW["raw/day.csv"]
        SCRIPTS["scripts/ · glue-jobs/"]
        FEAT["features/{ref_date}/features.parquet"]
        MET["metrics/{ref_date}/metrics.json"]
        MOD["models/{ref_date}/model.pkl"]
        PRED["predictions/ref_date={ref_date}/predictions.parquet"]
        ATHOUT["athena-results/"]
    end

    subgraph OBS["Observabilidade"]
        CWLOG["CloudWatch Logs<br/>/aws-glue/python-jobs"]
        CWMET["CloudWatch Metrics<br/>RMSE · MAE · RMSEThresholdBreached"]
        SNS["SNS pipeline-alerts"]
        ALM["Alarmes CW<br/>opcional · terraform flag"]
    end

    subgraph LAKE["Analytics"]
        GC["Glue Data Catalog<br/>DB bike_sharing<br/>Tabela predictions"]
        ATH["Athena Workgroup<br/>glue-b3-dev-athena-pipeline"]
        USR["Analista / BI / Console"]
    end

    EB --> SFN
    MANUAL --> SFN

    S02 --> GJ2
    S03 --> GJ3
    S04 --> GJ4
    S05 --> GJ5
    S07 --> ATH

    SCRIPTS -.->|deploy Terraform| GJ2 & GJ3 & GJ4 & GJ5

    RAW --> GJ2
    GJ2 --> FEAT
    FEAT --> GJ3
    GJ3 --> MET
    GJ3 --> MOD
    GJ3 --> CWMET
    MOD --> GJ4
    RAW --> GJ4
    FEAT --> GJ4
    GJ4 --> PRED
    PRED --> GJ5
    GJ5 --> GC

    GC --> ATH
    PRED --> ATH
    ATH --> ATHOUT
    ATH --> USR

    GJ2 & GJ3 & GJ4 & GJ5 --> CWLOG
    FAIL --> SNS
    CWMET -.-> ALM
    ALM -.-> SNS
```

## Esteira mensal — passo a passo (sequência)

Diagrama temporal de **uma execução** da SFN `monthly_pipeline`, com todos os serviços envolvidos:

```mermaid
sequenceDiagram
    autonumber
    participant EB as EventBridge
    participant DEV as Operador / Analista
    participant SFN as Step Functions<br/>monthly_pipeline
    participant S3 as Amazon S3
    participant G2 as Glue Job<br/>validate-day-csv
    participant G3 as Glue Job<br/>train-xgboost
    participant CW as CloudWatch
    participant G4 as Glue Job<br/>predict-xgboost
    participant G5 as Glue Job<br/>register-predictions-catalog
    participant GC as Glue Data Catalog
    participant ATH as Athena
    participant SNS as SNS Alertas

    alt Agendamento automático (dia 1 do mês)
        EB->>SFN: StartExecution (sem input)
        SFN->>SFN: ref_date = YYYY-MM-01 do mês atual
    else Teste manual
        DEV->>SFN: StartExecution {"ref_date":"2011-06-01"}
        SFN->>SFN: Usa ref_date do input
    end

    SFN->>SFN: Monta args: s3_input_path, database_name,<br/>athena_workgroup, rmse_threshold, namespace CW

    rect rgb(230, 245, 255)
        Note over SFN,S3: S2 — Features
        SFN->>G2: startJobRun.sync (--ref_date, --s3_input_path)
        G2->>S3: Lê raw/day.csv
        G2->>G2: Valida schema · filtra mês · seleciona features
        G2->>S3: Escreve features/{ref_date}/features.parquet
        G2->>CW: Logs Glue
        G2-->>SFN: SUCCEEDED
    end

    rect rgb(255, 243, 230)
        Note over SFN,CW: S3 — Treino + modelo
        SFN->>G3: startJobRun.sync (+ rmse_threshold, cloudwatch_namespace)
        G3->>S3: Lê features.parquet
        G3->>G3: Split 80/20 · XGBRegressor · RMSE/MAE
        G3->>S3: Escreve metrics/{ref_date}/metrics.json
        G3->>S3: Escreve models/{ref_date}/model.pkl
        G3->>CW: Publica métricas RMSE, MAE (S4-03)
        G3->>CW: Logs Glue
        G3-->>SFN: SUCCEEDED
    end

    rect rgb(230, 255, 230)
        Note over SFN,S3: S3-03 — Inferência
        SFN->>G4: startJobRun.sync
        G4->>S3: Carrega model.pkl
        G4->>S3: Lê day.csv + features do mês
        G4->>G4: Prediz cnt_pred para cada dia
        G4->>S3: Escreve predictions/ref_date={ref_date}/predictions.parquet
        G4->>CW: Logs Glue
        G4-->>SFN: SUCCEEDED
    end

    rect rgb(245, 230, 255)
        Note over SFN,GC: S4-01 — Catalog
        SFN->>G5: startJobRun.sync (+ database_name)
        G5->>S3: Lê predictions.parquet (schema)
        G5->>GC: Cria/atualiza bike_sharing.predictions<br/>partição ref_date
        G5->>CW: Logs Glue
        G5-->>SFN: SUCCEEDED
    end

    rect rgb(255, 230, 245)
        Note over SFN,ATH: S4-02 — Validação SQL
        SFN->>SFN: Monta SQL abs_error por dteday
        SFN->>ATH: startQueryExecution.sync (workgroup)
        ATH->>GC: Resolve tabela + partição
        ATH->>S3: Scan predictions via Catalog
        ATH->>S3: Resultado em athena-results/
        ATH-->>SFN: SUCCEEDED
    end

    SFN-->>DEV: Execution SUCCEEDED

    opt Qualquer Glue Job ou Athena falha
        SFN->>SNS: Publish [pipeline falhou]<br/>ref_date · execução · erro
        SFN-->>DEV: Execution FAILED
    end
```

### Tabela resumo dos passos

| # | Estado SFN | Serviço AWS | Script Glue | Entrada S3 | Saída S3 / destino |
|---|------------|-------------|-------------|------------|-------------------|
| 0 | `00_EscolherRefDate` | Step Functions | — | — | `ref_date` |
| 1 | `01_MontarArgumentos` | Step Functions | — | — | args consolidados |
| 2 | `Glue_S2_ValidarCSV_Features` | Glue | `validate_day_csv_job.py` | `raw/day.csv` | `features/{ref_date}/features.parquet` |
| 3 | `Glue_S3_TreinarXGBoost` | Glue + CloudWatch | `train_xgboost_job.py` | `features.parquet` | `metrics.json`, `model.pkl`, métricas CW |
| 4 | `Glue_S3_InferirPredicoes` | Glue | `predict_xgboost_job.py` | `model.pkl`, `day.csv` | `predictions/ref_date=…/predictions.parquet` |
| 5 | `Glue_S4_RegistrarGlueCatalog` | Glue + Catalog | `register_predictions_catalog_job.py` | `predictions.parquet` | Tabela `bike_sharing.predictions` |
| 6 | `Prep_S4_MontarQueryAthena` | Step Functions | — | — | SQL `abs_error` |
| 7 | `Athena_S4_ValidarPredicoes` | Athena | — | Catalog + S3 | `athena-results/` |
| ✗ | `Alerta_SNS_Falha` | SNS | — | — | E-mail / subscriber |

> **Fora da SFN mensal:** job `parse_args` (S1-02 smoke test) e SFN `validate-predictions` (Athena isolado) existem para testes pontuais — ver [S1-03](s1-03-step-functions.md).

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
