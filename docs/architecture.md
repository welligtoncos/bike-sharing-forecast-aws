# Arquitetura

Visão geral da infraestrutura provisionada pelo Terraform neste repositório.

## Diagrama de componentes

```mermaid
flowchart TB
    subgraph Orquestracao["Orquestração (futuro)"]
        SF[Step Functions]
    end

    subgraph Compute["Compute"]
        GJ[Glue Job Python Shell<br/>parse_args_job.py]
    end

    subgraph Storage["Armazenamento"]
        S3[(S3 Bucket pipeline)]
        RAW[raw/]
        FEAT[features/]
        PRED[predictions/]
        MOD[models/]
        SCR[scripts/]
    end

    subgraph Security["Segurança"]
        ROLE[IAM Role<br/>glue-b3-dev-iam-glue]
    end

    subgraph Observability["Observabilidade"]
        CW[CloudWatch Logs<br/>/aws-glue/python-jobs]
    end

    subgraph Catalog["Catálogo (futuro)"]
        GC[Glue Data Catalog<br/>database b3_raw]
    end

    SF -->|"StartJobRun<br/>--ref_date, --s3_input_path"| GJ
    GJ --> ROLE
    ROLE --> S3
    ROLE --> GC
    GJ --> CW
    S3 --> RAW
    S3 --> FEAT
    S3 --> PRED
    S3 --> MOD
    S3 --> SCR
    SCR -.->|script fonte| GJ
```

## Fluxo de dados previsto

```
1. CSV bruto          → s3://{bucket}/raw/
2. Feature engineering → s3://{bucket}/features/
3. Modelo treinado     → s3://{bucket}/models/
4. Previsões           → s3://{bucket}/predictions/
```

O Glue Job S1-02 é o **primeiro job** do pipeline: recebe a data de referência e o caminho S3 de entrada via argumentos, preparando a integração com Step Functions nas stories seguintes.

## Recursos AWS

| Recurso | Terraform | Nome (dev) |
|---------|-----------|------------|
| S3 Bucket | `aws_s3_bucket.pipeline` | `glue-b3-dev-s3-pipeline-{account}` |
| S3 Versioning | `aws_s3_bucket_versioning.pipeline` | Enabled |
| S3 Public Access Block | `aws_s3_bucket_public_access_block.pipeline` | Bloqueio total |
| S3 Folders | `aws_s3_object.folders` | `raw/`, `features/`, `predictions/`, `models/` |
| S3 Script | `aws_s3_object.glue_script_parse_args` | `scripts/parse_args_job.py` |
| IAM Role | `aws_iam_role.glue` | `glue-b3-dev-iam-glue` |
| IAM Policy S3 | `aws_iam_role_policy.glue_s3` | List/Get/Put/Delete no bucket |
| IAM Policy Catalog | `aws_iam_role_policy.glue_catalog` | Leitura Glue Catalog `b3_raw` |
| IAM Policy Logs | `aws_iam_role_policy.glue_logs` | Escrita em `/aws-glue/python-jobs` |
| Glue Job | `aws_glue_job.parse_args` | `glue-b3-dev-glue-job-parse-args` |

## IAM — quem acessa o quê

```mermaid
flowchart LR
    GLUE[glue.amazonaws.com] -->|AssumeRole| ROLE[glue-b3-dev-iam-glue]

    ROLE --> P1[AWSGlueServiceRole<br/>managed policy]
    ROLE --> P2[glue-s3<br/>bucket pipeline]
    ROLE --> P3[glue-catalog<br/>database b3_raw]
    ROLE --> P4[glue-logs<br/>CloudWatch]
```

| Policy | Escopo | Finalidade |
|--------|--------|------------|
| `AWSGlueServiceRole` | AWS managed | Operações padrão Glue |
| `glue-s3` | Bucket pipeline | Ler/gravar CSVs, modelos, scripts |
| `glue-catalog` | Database `b3_raw` | Consultar tabelas e partições |
| `glue-logs` | `/aws-glue/python-jobs` | Registrar stdout e logs do job |

## Arquivos Terraform por domínio

| Arquivo | Responsabilidade |
|---------|------------------|
| `main.tf` | Provider AWS, bucket S3, versionamento, pastas |
| `iam.tf` | Role e policies do Glue |
| `glue.tf` | Upload do script + definição do Glue Job |
| `locals.tf` | Nomenclatura centralizada |
| `variables.tf` | Entrada configurável |
| `outputs.tf` | Valores para scripts e integrações |

## Tags padrão

Aplicadas via `default_tags` no provider:

```
Project     = glue-b3
Environment = dev
ManagedBy   = terraform
Name        = <nome-do-recurso>
```

## Integração Step Functions (visão futura)

O Step Functions invocará o Glue Job passando argumentos dinâmicos:

```json
{
  "Type": "Task",
  "Resource": "arn:aws:states:::glue:startJobRun.sync",
  "Parameters": {
    "JobName": "glue-b3-dev-glue-job-parse-args",
    "Arguments": {
      "--ref_date.$": "$.ref_date",
      "--s3_input_path.$": "$.s3_input_path"
    }
  }
}
```

Detalhes em [S1-02 — Glue Job](s1-02-glue-job.md).
