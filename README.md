# project-glue-3 — Pipeline de Previsão de Demanda (AWS)

Infraestrutura como código (Terraform) para um **pipeline de previsão de demanda operacional** que roda automaticamente todo mês na AWS — orquestrado por Step Functions, processado por Glue Jobs e persistido no S3 para consulta no Athena.

> Neste repositório, a métrica simulada é **aluguéis de bike** (Bike Sharing). No contexto real, substitua por qualquer indicador que você precise prever com antecedência: vendas, chamados, consumo, acessos, volume de transações.

## O que o projeto simula

Um pipeline de ML de ponta a ponta que, **no primeiro dia de cada mês**, dispara sozinho, lê o histórico do período anterior, gera a previsão do comportamento futuro e deixa o resultado pronto para consulta — **sem intervenção humana**.

## Arquitetura

```mermaid
flowchart TB
    subgraph AGENDAMENTO["Agendamento · S1-03 ✅"]
        EB["EventBridge<br/>cron: dia 1 / mês · 06:00 UTC"]
    end

    subgraph ORQUESTRACAO["Orquestração · S1-03 ✅"]
        SF["Step Functions<br/>monthly_pipeline.asl"]
        BUILD["BuildArguments<br/>ref_date = YYYY-MM-01"]
        RUN["RunGlueJob · sync"]
        FAIL["NotifyFailure → SNS"]
    end

    subgraph COMPUTE["Glue Jobs Python Shell"]
        GJ1["parse_args_job.py<br/>S1-02 ✅"]
        GJ2["validate_day_csv_job.py<br/>S2 ✅"]
        GJ3["train_xgboost_job.py<br/>S3-01 ✅"]
        S2A["① Validar schema"]
        S2B["② Filtrar dteday"]
        S2C["③ Parquet features"]
        S3A["④ XGBRegressor<br/>split 80/20"]
        S3B["⑤ RMSE + MAE"]
    end

    subgraph STORAGE["S3 pipeline bucket · S1-01 ✅"]
        S3[("glue-b3-dev-s3-pipeline")]
        RAW["raw/day.csv"]
        FEAT["features/{ref_date}/features.parquet"]
        MET["metrics/{ref_date}/metrics.json"]
        PRED["predictions/ · futuro"]
        MOD["models/ · futuro"]
    end

    subgraph OBS["Observabilidade"]
        CW["CloudWatch Logs ✅"]
        SNS["SNS Alertas ✅"]
        ALM["Alarmes RMSE · futuro"]
    end

    subgraph ANALYTICS["Consulta · futuro"]
        GC["Glue Catalog · b3_raw"]
        ATH["Athena · cnt_real vs cnt_pred"]
        USR["Time de negócio / BI"]
    end

    EB --> SF
    SF --> BUILD --> RUN
    RUN -->|"--ref_date<br/>--s3_input_path"| GJ1
    RUN -.-> FAIL

    GJ2 --> S2A --> S2B --> S2C
    RAW --> GJ2
    S2C --> FEAT

    FEAT --> GJ3
    GJ3 --> S3A --> S3B
    S3B --> MET

    GJ1 --> CW
    GJ2 --> CW
    GJ3 --> CW
    FAIL --> SNS
    ALM -.-> SNS

    S3 --- RAW
    S3 --- FEAT
    S3 --- MET
    S3 --- PRED
    S3 --- MOD

    FEAT --> GC
    PRED --> GC
    GC --> ATH --> USR

    classDef done fill:#d4edda,stroke:#28a745,color:#155724
    classDef future fill:#fff3cd,stroke:#ffc107,color:#856404

    class EB,SF,BUILD,RUN,GJ1,GJ2,GJ3,S2A,S2B,S2C,S3A,S3B,S3,RAW,FEAT,MET,CW,SNS,FAIL done
    class PRED,MOD,ALM,GC,ATH,USR future
```

Legenda: **verde** = implementado (Sprint 1 + 2 + 3) · **amarelo** = próximas stories (inferência, persistência do modelo, Athena, alarmes).

### Fluxo de dados (Sprint 2 → Sprint 3)

```mermaid
flowchart LR
    A["raw/day.csv"] --> B["Validar schema"]
    B --> C["Filtrar ref_date"]
    C --> D["features.parquet"]
    D --> E["X / y split 80/20"]
    E --> F["XGBRegressor"]
    F --> G["metrics.json<br/>RMSE + MAE"]

    style A fill:#d4edda
    style B fill:#d4edda
    style C fill:#d4edda
    style D fill:#d4edda
    style E fill:#d4edda
    style F fill:#d4edda
    style G fill:#d4edda
```

| Etapa | Story | Entrada → Saída |
|-------|-------|-----------------|
| 1. Disparo | S1-03 | EventBridge → Step Functions |
| 2. Argumentos | S1-03 | `ref_date` + `s3://…/raw/day.csv` |
| 3. Validar schema | S2-01 | CSV → colunas obrigatórias |
| 4. Filtrar mês | S2-02 | `dteday` no mês/ano de `ref_date` |
| 5. Salvar features | S2-03 | Parquet em `features/{ref_date}/` |
| 6. Treinar modelo | S3-01 | Parquet → XGBoost + `metrics/{ref_date}/metrics.json` |
| 7. Inferência | futuro | Previsões em `predictions/` |
| 8. Consulta | futuro | Athena → `cnt_pred` vs `cnt_real` |

### O problema que resolve

| Sem pipeline | Com pipeline |
|--------------|--------------|
| Alguém puxa os dados manualmente | Step Functions dispara no dia 1 |
| Roda o modelo no notebook local | Glue Job executa na AWS |
| Salva o resultado em planilha/pasta | Resultado versionado no S3 |
| Avisa o time por e-mail/Slack manual | SNS + CloudWatch em caso de falha |

Hoje, sem automação, o fluxo é **lento, propenso a erro e não escala**. Este projeto modela a solução corporativa: agendamento, execução, persistência e observabilidade integrados.

### Perguntas de negócio que o pipeline responde

| Pergunta | Resposta do pipeline |
|----------|----------------------|
| Qual será a demanda do próximo período? | Predição `cnt_pred` por dia (futuro) |
| O modelo está acertando? | RMSE/MAE em `metrics.json` · futuro: `cnt_real` vs `cnt_pred` |
| Quando o pipeline falhou ou degradou? | Alarmes CloudWatch + log de métricas |

### Por que Bike Sharing?

O dataset de Bike Sharing tem **sazonalidade** (temperatura, estação do ano, dia da semana) — o mesmo tipo de padrão que modelos como XGBoost capturam bem e que aparece em problemas reais: previsão de estoque, ocupação hospitalar, volume de transações ou, neste projeto, métricas financeiras como série histórica da B3.

> **Dica:** o dataset cobre **2011–2012**. Use `ref_date=2011-06-01` (ou outro mês desse intervalo) nos testes manuais.

## O que já está implementado

### Sprint 1 — Infraestrutura e orquestração

| Story | Entrega | Status |
|-------|---------|--------|
| S1-01 | Bucket S3 (`raw/`, `features/`, `metrics/`, `predictions/`, `models/`) + IAM Glue | ✅ |
| S1-02 | Glue Job `parse_args` (`--ref_date`, `--s3_input_path`) | ✅ |
| S1-03 | Step Functions + agendamento mensal + alertas SNS | ✅ |

### Sprint 2 — Ingestão e features

| Story | Entrega | Status |
|-------|---------|--------|
| S2-01 | Validar schema do `day.csv` (pandas + s3fs) | ✅ |
| S2-02 | Filtrar por `ref_date` (mês/ano de `dteday`) | ✅ |
| S2-03 | Salvar Parquet em `features/{ref_date}/features.parquet` | ✅ |

### Sprint 3 — Treino do modelo

| Story | Entrega | Status |
|-------|---------|--------|
| S3-01 | XGBRegressor, split 80/20 (`random_state=42`), RMSE/MAE no CloudWatch e `metrics/{ref_date}/metrics.json` | ✅ |

Próximas stories: serializar modelo em `models/`, inferência → `predictions/`, Glue Catalog, queries Athena.

## Início rápido

```powershell
# 1. Verificar credenciais AWS
aws sts get-caller-identity

# 2. Configurar variáveis
Copy-Item terraform.tfvars.example terraform.tfvars
# Edite aws_account_id com o Account da saída acima

# 3. Provisionar
terraform init
terraform apply -var-file="terraform.tfvars"

# 4. Testes locais
pip install -r requirements-dev.txt
python -m pytest tests/ -v

# 5. Testar o pipeline (Step Functions)
$SFN = terraform output -raw sfn_monthly_pipeline_arn
aws stepfunctions start-execution `
  --state-machine-arn $SFN `
  --name "test-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
```

## Executar Glue Jobs manualmente (PowerShell)

No PowerShell, **não use `\"`** dentro de `--arguments` — isso gera JSON inválido. Use uma das opções abaixo.

### Opção A — aspas simples (recomendado)

```powershell
$bucket = terraform output -raw s3_bucket_name
$ref    = "2011-06-01"

# S2 — gerar features Parquet
aws glue start-job-run `
  --job-name glue-b3-dev-glue-job-validate-day-csv `
  --arguments "{`"--ref_date`":`"$ref`",`"--s3_input_path`":`"s3://$bucket/raw/day.csv`"}"

# S3 — treinar XGBoost (requer features.parquet do passo anterior)
aws glue start-job-run `
  --job-name glue-b3-dev-glue-job-train-xgboost `
  --arguments "{`"--ref_date`":`"$ref`",`"--s3_input_path`":`"s3://$bucket/raw/day.csv`"}"
```

Alternativa com JSON literal (sem variáveis):

```powershell
aws glue start-job-run `
  --job-name glue-b3-dev-glue-job-train-xgboost `
  --arguments '{"--ref_date":"2011-06-01","--s3_input_path":"s3://glue-b3-dev-s3-pipeline-303238378103/raw/day.csv"}'
```

### Opção B — arquivo JSON

Crie `glue-args.json` (não commitar — está no `.gitignore` como `args.json`):

```json
{
  "--ref_date": "2011-06-01",
  "--s3_input_path": "s3://glue-b3-dev-s3-pipeline-303238378103/raw/day.csv"
}
```

```powershell
aws glue start-job-run `
  --job-name glue-b3-dev-glue-job-train-xgboost `
  --arguments file://glue-args.json
```

### Validar execução

```powershell
# Status do último run
aws glue get-job-runs `
  --job-name glue-b3-dev-glue-job-train-xgboost `
  --max-results 1 `
  --query "JobRuns[0].{State:JobRunState,Error:ErrorMessage}"

# Métricas no S3
aws s3 cp "s3://$bucket/metrics/$ref/metrics.json" -
```

**Critérios S3-01:** `JobRunState=SUCCEEDED`, log com `RMSE=` e `MAE=`, JSON com `"random_state": 42`, `"test_size": 0.2`.

> Jobs Python Shell rodam **1 execução por vez** — aguarde o run anterior terminar.

## Documentação

| Documento | Conteúdo |
|-----------|----------|
| [Getting Started](docs/getting-started.md) | Pré-requisitos, deploy, validação |
| [Arquitetura](docs/architecture.md) | Fluxo de dados, recursos AWS, IAM |
| [S1-01 — Bucket S3](docs/s1-01-s3-bucket.md) | Estrutura de pastas e versionamento |
| [S1-02 — Glue Job](docs/s1-02-glue-job.md) | Argumentos, execução, logs |
| [S1-03 — Step Functions](docs/s1-03-step-functions.md) | Agendamento mensal, ASL, SNS, EventBridge |

## Estrutura do repositório

```
project-glue-3/
├── main.tf              # S3 bucket, versionamento, pastas
├── iam.tf               # Role Glue + policies S3/Catalog/Logs
├── glue.tf              # Glue Job parse_args (S1-02)
├── glue_validate.tf     # Glue Job validate_day_csv (S2)
├── glue_train.tf        # Glue Job train_xgboost (S3-01)
├── stepfunctions.tf     # State machine, EventBridge, SNS (S1-03)
├── stepfunctions_iam.tf
├── stepfunctions/
│   └── monthly_pipeline.asl.json.tpl
├── scripts/
│   ├── parse_args_job.py       # S1-02
│   ├── validate_day_csv_job.py # S2 entry point
│   ├── schema_validation.py    # S2 módulo compartilhado
│   ├── train_xgboost_job.py    # S3-01 entry point
│   └── xgboost_training.py     # S3-01 treino + métricas
├── tests/
└── docs/
```

## Outputs principais

```powershell
terraform output s3_bucket_name                       # bucket pipeline
terraform output -raw sfn_monthly_pipeline_arn        # Step Functions
terraform output -raw glue_job_validate_day_csv_name  # job S2 (features Parquet)
terraform output -raw glue_job_train_xgboost_name     # job S3-01 (treino)
terraform output features_parquet_uri_template        # s3://…/features/{ref_date}/features.parquet
terraform output metrics_json_uri_template            # s3://…/metrics/{ref_date}/metrics.json
```
