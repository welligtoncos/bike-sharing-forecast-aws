# Guia do usuário — dataset, tabelas e uso do modelo

Documento para **analistas, operação e negócio** que consomem as predições do pipeline. Não exige conhecimento de Terraform ou Glue.

---

## Dataset utilizado

### Origem

| Item | Descrição |
|------|-----------|
| **Nome** | Bike Sharing Dataset (UCI / Capital Bikeshare) |
| **Arquivo no pipeline** | `s3://{bucket}/raw/day.csv` |
| **Granularidade** | **Um registro por dia** (série diária agregada) |
| **Período histórico** | **2011 e 2012** (use `ref_date` dentro desse intervalo nos testes, ex.: `2011-06-01`) |
| **Métrica alvo** | Número total de **aluguéis de bicicletas por dia** (`cnt`) em toda a rede |

> **Importante:** este projeto **não** prevê demanda **por estação/hub**. A predição é a **soma diária** de aluguéis na rede. Para planejamento por ponto, é necessário enriquecer o dataset (ver [Limitações](#limitações-e-próximos-passos)).

### Referência

- [UCI Machine Learning Repository — Bike Sharing Dataset](https://archive.ics.uci.edu/ml/datasets/bike+sharing+dataset)
- Variável `cnt` = `casual` + `registered` (usuários ocasionais + registrados)

---

## Descrição das tabelas e arquivos

### 1. Entrada bruta — `raw/day.csv`

CSV no S3 com o histórico diário. Colunas **presentes no arquivo original** (referência UCI):

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `instant` | int | Índice sequencial do registro |
| `dteday` | date | Data do dia (ex.: `2011-06-01`) |
| `season` | int | Estação do ano (1=primavera … 4=inverno) |
| `yr` | int | Ano (0=2011, 1=2012 no dataset codificado) |
| `mnth` | int | Mês (1–12) |
| `holiday` | int | 1 se feriado, 0 caso contrário |
| `weekday` | int | Dia da semana (0=dom … 6=sáb) |
| `workingday` | int | 1 se dia útil e não feriado |
| `weathersit` | int | Clima (1=limpo, 2=nublado/névoa, 3=chuva/neve leve, 4=chuva forte) |
| `temp` | float | Temperatura normalizada (~0–1) |
| `atemp` | float | Sensação térmica normalizada |
| `hum` | float | Umidade normalizada (~0–1) |
| `windspeed` | float | Velocidade do vento normalizada |
| `casual` | int | Aluguéis de usuários ocasionais no dia |
| `registered` | int | Aluguéis de usuários registrados no dia |
| **`cnt`** | **int** | **Total de aluguéis no dia (alvo do modelo)** |

#### Colunas usadas pelo modelo (features)

O pipeline **seleciona apenas** estas colunas para treino e predição:

| Coluna | Papel no modelo |
|--------|-----------------|
| `season` | Sazonalidade anual |
| `temp` | Temperatura |
| `hum` | Umidade (proxy parcial de clima) |
| `windspeed` | Vento |
| `weekday` | Dia da semana |
| `cnt` | Variável alvo (o que queremos prever) |

Colunas **não usadas** hoje (mas existem no CSV): `holiday`, `weathersit`, `workingday`, `casual`, `registered`, etc. Incluí-las no futuro melhora perguntas sobre **feriado** e **chuva**.

---

### 2. Features processadas — `features/{ref_date}/features.parquet`

Gerado pelo job **validate-day-csv** (S2). Contém só as colunas de modelagem do mês `ref_date`:

| Coluna | Descrição |
|--------|-----------|
| `season`, `temp`, `hum`, `windspeed`, `weekday` | Entradas do XGBoost |
| `cnt` | Valor real observado (target) |

---

### 3. Saída para o usuário — `bike_sharing.predictions` (Athena)

Tabela registrada no **Glue Catalog**, consultável no **Athena**. Particionada por mês de referência (`ref_date`).

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| **`dteday`** | string/date | Dia calendário (ex.: `2011-06-15`) |
| **`cnt_real`** | bigint | Aluguéis **reais** observados naquele dia |
| **`cnt_pred`** | double | Aluguéis **previstos** pelo modelo naquele dia |
| **`ref_date`** | string (partição) | Mês de competência do pipeline (ex.: `2011-06-01` = junho/2011) |

**Localização S3:** `s3://{bucket}/predictions/ref_date={ref_date}/predictions.parquet`

**Workgroup Athena:** `glue-b3-dev-athena-pipeline`  
**Database:** `bike_sharing`

---

### 4. Métricas de qualidade — `metrics/{ref_date}/metrics.json`

Arquivo JSON gerado no treino (uso técnico / auditoria):

| Campo | Significado para negócio |
|-------|--------------------------|
| `rmse` | Erro quadrático médio — quanto menor, melhor |
| `mae` | Erro absoluto médio em número de aluguéis |
| `ref_date` | Mês treinado |
| `model_reused` | Se reutilizou modelo já salvo (`true`/`false`) |

---

## 1. Como o usuário testa / usa o modelo

### Pré-requisito

A esteira mensal (ou jobs manuais S2→S4) já rodou para o mês desejado. Exemplo de teste: **`ref_date = 2011-06-01`**.

Verificar se há dados:

```powershell
$BUCKET = terraform output -raw s3_bucket_name
aws s3 ls "s3://$BUCKET/predictions/ref_date=2011-06-01/"
```

---

### Passo 1 — Abrir o Athena

1. Console AWS → **Athena**
2. **Workgroup:** `glue-b3-dev-athena-pipeline`
3. **Database:** `bike_sharing`
4. Query editor

Ou use a query pronta:

```powershell
terraform output athena_query_predictions_example
```

---

### Passo 2 — Validação: modelo vs gabarito (duas consultas)

A tabela `bike_sharing.predictions` guarda **`cnt_pred`** (o que o modelo prevê) e **`cnt_real`** (gabarito — o que de fato ocorreu). Para validar, rode as duas consultas abaixo ou a consulta combinada do [Passo 3](#passo-3--comparar-previsão-vs-realidade-teste-completo-do-modelo).

Substitua `ref_date` pelo mês desejado (ex.: `2011-06-01`).

#### Consulta A — O que o **modelo prevê**

```sql
SELECT
    dteday,
    cnt_pred AS alugueis_previstos
FROM bike_sharing.predictions
WHERE ref_date = '2011-06-01'
ORDER BY dteday;
```

Uso: **planejamento** — demanda esperada por dia, sem olhar o valor real.

#### Consulta B — **Gabarito** (valor real)

```sql
SELECT
    dteday,
    cnt_real AS alugueis_reais
FROM bike_sharing.predictions
WHERE ref_date = '2011-06-01'
ORDER BY dteday;
```

Uso: **conferência** — histórico observado (ground truth) do mesmo período.

> Compare dia a dia: para cada `dteday`, `alugueis_previstos` (A) deve estar próximo de `alugueis_reais` (B). Diferenças grandes indicam dias atípicos ou features faltantes (feriado, chuva explícita, etc.).

---

### Passo 3 — Comparar previsão vs realidade (teste completo do modelo)

Cole e execute (ajuste `ref_date` se necessário):

```sql
SELECT
    dteday,
    cnt_real,
    cnt_pred,
    cnt_pred - cnt_real AS erro,
    ABS(cnt_real - cnt_pred) AS abs_error,
    ROUND(100.0 * ABS(cnt_real - cnt_pred) / NULLIF(cnt_real, 0), 1) AS erro_pct
FROM bike_sharing.predictions
WHERE ref_date = '2011-06-01'
ORDER BY dteday;
```

**Como interpretar:**

| Coluna | O que significa |
|--------|-----------------|
| `cnt_pred` | Demanda **esperada** de aluguéis na rede naquele dia |
| `cnt_real` | Demanda **que de fato ocorreu** (histórico) |
| `erro_pct` | Erro percentual; **&lt; 15–20%** em muitos dias indica modelo útil para planejamento |
| Tendência ao longo do mês | Sazonalidade e dias atípicos |

> Em **produção futura**, `cnt_real` do mês corrente pode não existir ainda — aí `cnt_pred` vira **planejamento**, e a validação ocorre no mês seguinte.

---

### Passo 4 — Resumo do mês (KPIs para reunião)

```sql
SELECT
    ref_date,
    COUNT(*) AS dias,
    ROUND(AVG(cnt_real), 0) AS media_real,
    ROUND(AVG(cnt_pred), 0) AS media_prevista,
    ROUND(AVG(ABS(cnt_real - cnt_pred)), 0) AS mae_diario,
    ROUND(MAX(ABS(cnt_real - cnt_pred)), 0) AS pior_erro_dia
FROM bike_sharing.predictions
WHERE ref_date = '2011-06-01'
GROUP BY ref_date;
```

Compare `mae_diario` com o JSON de treino:

```powershell
aws s3 cp "s3://$BUCKET/metrics/2011-06-01/metrics.json" -
```

Os valores devem ser **coerentes** (mesma ordem de grandeza).

---

### Passo 5 — Dias com maior e menor demanda prevista

**Planejar frota total** (não por estação):

```sql
-- Top 5 dias mais movimentados (previsto)
SELECT dteday, cnt_pred, cnt_real
FROM bike_sharing.predictions
WHERE ref_date = '2011-06-01'
ORDER BY cnt_pred DESC
LIMIT 5;

-- Top 5 dias mais calmos (previsto) — candidatos a janela de manutenção
SELECT dteday, cnt_pred, cnt_real
FROM bike_sharing.predictions
WHERE ref_date = '2011-06-01'
ORDER BY cnt_pred ASC
LIMIT 5;
```

**Regra operacional sugerida:** frota em circulação ≈ `cnt_pred × margem de segurança (ex.: 1,10)`.

---

### Passo 6 — Onde o modelo erra mais (auditoria)

```sql
SELECT dteday, cnt_real, cnt_pred, ABS(cnt_real - cnt_pred) AS abs_error
FROM bike_sharing.predictions
WHERE ref_date = '2011-06-01'
ORDER BY abs_error DESC
LIMIT 10;
```

Dias com erro alto costumam ser **eventos não modelados** (feriado, clima extremo, mudança operacional) — hoje o pipeline **não** inclui `holiday` nem `weathersit` explicitamente.

---

### Passo 7 — Disparar validação via Step Functions (opcional)

Sem escrever SQL manualmente:

```powershell
$SFN = terraform output -raw sfn_validate_predictions_arn
aws stepfunctions start-execution `
  --state-machine-arn $SFN `
  --input '{"ref_date":"2011-06-01"}'
```

Sucesso = query Athena executada; resultados em `s3://{bucket}/athena-results/`.

---

### Passo 8 — Esteira completa (gerar predições do zero)

```powershell
$SFN = terraform output -raw sfn_monthly_pipeline_arn
aws stepfunctions start-execution `
  --state-machine-arn $SFN `
  --name "usuario-teste-$(Get-Date -Format 'yyyyMMdd')" `
  --input '{"ref_date":"2011-06-01"}'
```

Aguarde `SUCCEEDED` (~10–20 min), depois repita os passos 2–6 no Athena.

---

## Uso prático das predições (negócio)

| Pergunta | O que fazer com `cnt_pred` |
|----------|----------------------------|
| Quantas bikes colocar na rua **no total**? | Usar `cnt_pred` + margem (~10%) |
| Quantas bikes **por estação**? | **Não coberto** — ratear `cnt_pred` por regra interna ou dados por estação |
| Quando fazer **manutenção**? | Priorizar dias com `cnt_pred` abaixo da mediana do mês |
| Demanda cai com **chuva/feriado**? | **Parcial** — umidade/vento entram no modelo; feriado/chuva explícitos exigem evolução do dataset |

---

## Limitações e próximos passos

| Limitação atual | Evolução possível |
|-----------------|-------------------|
| Agregado diário (rede inteira) | Modelo por estação ou região |
| Sem coluna `holiday` / `weathersit` no treino | Incluir no `schema_validation.py` e retreinar |
| Manutenção de frota não modelada | Integrar ERP ou regras sobre dias de baixa demanda |
| Consumo só via Athena/SQL | Dashboard QuickSight conectado ao Glue Catalog |

---

## Ver também

| Documento | Público |
|-----------|---------|
| [S4-02 — Query Athena](s4-02-athena-query.md) | SQL técnico e SFN |
| [Guia de testes da esteira](pipeline-testing-guide.md) | Devs — validação end-to-end |
| [Casos de uso comerciais](commercial-use-cases.md) | Adaptar o padrão a outros negócios |
