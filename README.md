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
        RUN["RunGlueJob<br/>startJobRun.sync"]
        FAIL["NotifyFailure → SNS"]
    end

    subgraph COMPUTE["Processamento · S1-02 ✅"]
        GJ["Glue Job Python Shell<br/>parse_args_job.py"]
    end

    subgraph STORAGE["Armazenamento · S1-01 ✅"]
        S3[("S3 pipeline bucket")]
        RAW["raw/<br/>day.csv · histórico"]
        FEAT["features/<br/>variáveis sazonais"]
        PRED["predictions/<br/>cnt_pred por dia"]
        MOD["models/<br/>artefato XGBoost"]
    end

    subgraph OBS["Observabilidade"]
        CW["CloudWatch Logs<br/>/aws-glue/python-jobs · ✅"]
        SNS["SNS Alertas<br/>falha do job · ✅"]
        ALM["Alarmes RMSE<br/>degradação · futuro"]
    end

    subgraph ANALYTICS["Consulta · futuro"]
        GC["Glue Data Catalog<br/>b3_raw"]
        ATH["Athena<br/>cnt_real vs cnt_pred + RMSE"]
        USR["Time de negócio<br/>dashboards / BI"]
    end

    EB -->|"StartExecution"| SF
    SF --> BUILD --> RUN
    RUN -->|"Arguments:<br/>--ref_date<br/>--s3_input_path"| GJ
    RUN -.->|"States.ALL"| FAIL

    GJ -->|"lê entrada"| RAW
    GJ -->|"logs"| CW
    GJ -.->|"feature eng."| FEAT
    GJ -.->|"treino / inferência"| MOD
    GJ -.->|"salva previsão"| PRED

    S3 --- RAW
    S3 --- FEAT
    S3 --- PRED
    S3 --- MOD

    FAIL --> SNS
    ALM -.-> SNS

    PRED --> GC
    RAW --> GC
    GC --> ATH --> USR

    classDef done fill:#d4edda,stroke:#28a745,color:#155724
    classDef future fill:#fff3cd,stroke:#ffc107,color:#856404

    class EB,SF,BUILD,RUN,GJ,S3,RAW,CW,SNS,FAIL done
    class FEAT,PRED,MOD,ALM,GC,ATH,USR future
```

Legenda: nós verdes = **Sprint 1 implementado** · nós amarelos = **próximas stories** (XGBoost, inferência, Athena, alarmes de RMSE).

### Fluxo resumido

| Etapa | Quem executa | Entrada → Saída |
|-------|--------------|-----------------|
| 1. Disparo | EventBridge (dia 1) | calendário → Step Functions |
| 2. Argumentos | Step Functions | `ref_date` + `s3://…/raw/day.csv` |
| 3. Processamento | Glue Job | CSV histórico → features / modelo / predição |
| 4. Persistência | S3 | `predictions/` versionado |
| 5. Consulta | Athena | `cnt_pred` vs `cnt_real`, RMSE |
| 6. Falha | SNS + CloudWatch | alerta automático ao time |

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
| Qual será a demanda do próximo período? | Predição `cnt_pred` por dia |
| O modelo está acertando? | Comparação `cnt_real` vs `cnt_pred` + RMSE |
| Quando o pipeline falhou ou degradou? | Alarmes CloudWatch + log de métricas |

### Por que Bike Sharing?

O dataset de Bike Sharing tem **sazonalidade** (temperatura, estação do ano, dia da semana) — o mesmo tipo de padrão que modelos como XGBoost capturam bem e que aparece em problemas reais: previsão de estoque, ocupação hospitalar, volume de transações ou, neste projeto, métricas financeiras como série histórica da B3.

## O que já está implementado (Sprint 1)

| Story | Entrega | Status |
|-------|---------|--------|
| S1-01 | Bucket S3 (`raw/`, `features/`, `predictions/`, `models/`) + IAM Glue | ✅ |
| S1-02 | Glue Job Python Shell (`--ref_date`, `--s3_input_path`) | ✅ |
| S1-03 | Step Functions + agendamento mensal + alertas SNS | ✅ |

As stories seguintes completam o ciclo: feature engineering, treino XGBoost, inferência, tabelas Glue Catalog e queries Athena sobre `cnt_pred` / `cnt_real`.

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

# 4. Testar o pipeline (Step Functions)
$SFN = terraform output -raw sfn_monthly_pipeline_arn
aws stepfunctions start-execution `
  --state-machine-arn $SFN `
  --name "test-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
```

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
├── glue.tf              # Glue Job Python Shell + upload do script
├── stepfunctions.tf     # State machine, EventBridge, SNS (S1-03)
├── stepfunctions_iam.tf # IAM Step Functions e EventBridge
├── stepfunctions/
│   └── monthly_pipeline.asl.json.tpl
├── scripts/
│   └── parse_args_job.py   # Glue Job — leitura de argumentos (S1-02)
└── docs/
```

## Outputs principais

```powershell
terraform output s3_bucket_name              # bucket pipeline
terraform output glue_job_parse_args_name    # Glue Job
terraform output -raw sfn_monthly_pipeline_arn  # Step Functions
terraform output glue_role_arn               # role para novos jobs Glue
```
