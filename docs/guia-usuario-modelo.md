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

### Passo 9 — Teste local do modelo (24 meses, ~2 min)

Para validar treino e métricas em **todo o dataset** sem rodar Glue/Step Functions, use a **Fase 1B** do [Guia de testes da esteira](pipeline-testing-guide.md#fase-1b--teste-completo-do-modelo-local-24-meses):

```powershell
cd c:\welligton-aws\project-glue-3
pip install -r requirements-dev.txt
python -m pytest tests/ -v

$bucket = terraform output -raw s3_bucket_name
python scripts/simulate_monthly_evolution.py `
  --input-path "s3://$bucket/raw/day.csv" --mode both --output evolution_report.csv
python scripts/plot_evolution_report.py
```

**Saídas:** `evolution_report.csv`, `evolution_report.png`, `evolution_report.xlsx`.

| Modo | O que simula |
|------|----------------|
| `pipeline` | Esteira AWS: treino só no mês (~30 dias), split 80/20 |
| `walk_forward` | Histórico acumulado → avalia o mês inteiro |
| `both` | As duas curvas (47 linhas no CSV) |

Sem AWS: coloque `day.csv` em `data/` e use `--input-path data/day.csv` (detalhes no guia de testes).

> Este passo é **análise offline**. A validação em produção (S3, predições, Athena) continua nos Passos 7–8 ou na Fase 2 do guia de testes.

---

## Como interpretar o `evolution_report.csv`

Este arquivo resume **24 meses** (jan/2011–dez/2012) do Bike Sharing. Use-o para entender **tendências** e **limites** do modelo — não como número único de “qualidade oficial” em produção.

### Estrutura do arquivo

| Coluna | Significado | Como ler |
|--------|-------------|----------|
| `ref_date` | Mês analisado (`YYYY-MM-01`) | Eixo do tempo nos gráficos |
| `mode` | `pipeline` ou `walk_forward` | **Sempre filtre por modo** antes de comparar meses |
| `n_train` | Dias usados no **treino** | Cresce no walk-forward (31 → 700); fixo ~24 no pipeline |
| `n_eval` | Dias usados na **avaliação** | Pipeline: ~6–7 (20% do mês). Walk-forward: **mês inteiro** |
| `n_days_in_month` | Dias disponíveis no CSV naquele mês | 28–31 (fevereiro tem 28/29) |
| `rmse` | Erro quadrático médio (raiz) | Em **bicicletas/dia**; penaliza erros grandes |
| `mae` | Erro absoluto médio | Em **bicicletas/dia**; mais intuitivo para negócio |

**Unidade das métricas:** `rmse` e `mae` estão na mesma unidade de `cnt` (total de aluguéis no dia). Ex.: `mae = 500` ≈ “em média erramos 500 bikes por dia” naquele conjunto de avaliação.

**Ordem no CSV:** primeiro vêm os 24 meses em `pipeline`, depois os 23 meses em `walk_forward` (falta jan/2011 por não haver histórico).

---

### Dois modos — perguntas diferentes

```text
                    pipeline                          walk_forward
                    --------                          ------------
Treino              Só aquele mês (~24 dias)          Todo histórico ANTES do mês
Avaliação           ~20% do mês (6–7 dias)            Mês inteiro (28–31 dias)
Simula              Esteira AWS mensal                “Prever o próximo mês com o passado”
```

| Se você quer saber… | Olhe para… |
|---------------------|------------|
| O que acontece **hoje na AWS** quando rodamos um `ref_date` | `mode = pipeline` |
| Se **acumular histórico** melhoraria previsões mês a mês | `mode = walk_forward` |
| Erro médio **operacional** (“quantas bikes erramos por dia?”) | **`mae`** (mais legível) |
| Meses com **picos de erro** (outliers pesam) | **`rmse`** |

> **Não compare RMSE de `pipeline` com RMSE de `walk_forward` na mesma linha.** São desenhos de avaliação diferentes (amostra pequena vs mês completo).

---

### Leitura do seu relatório (dados reais)

#### Modo `pipeline` — o que a esteira AWS faz hoje

| Indicador | Valor no seu CSV | Interpretação |
|-----------|------------------|---------------|
| Meses | 24 | Jan/2011 a dez/2012 |
| RMSE médio | **~802** bikes/dia | Oscila muito mês a mês |
| MAE médio | **~572** bikes/dia | Referência rápida de erro típico |
| Melhor mês | **jun/2012** — RMSE 310, MAE 275 | Validação sorteou dias “fáceis” + poucos dados |
| Pior mês | **out/2012** — RMSE 1802, MAE 1111 | Pouco treino + alta variabilidade do mês |

**Padrão esperado:** linha **instável** no gráfico. Com ~24 dias de treino e só 6–7 dias de validação, o número **varia bastante sem significar que o modelo “piorou” de verdade** — é efeito de amostra pequena e sorteio 80/20.

**Para operação:** se você roda a SFN com `ref_date = 2011-06-01`, o `metrics.json` daquele mês reflete essa lógica (não o desempenho em todos os 30 dias de junho).

#### Modo `walk_forward` — evolução com dataset acumulado

| Fase | Período | RMSE típico | O que mostra |
|------|---------|-------------|--------------|
| Crescimento do histórico | fev/2011 – dez/2011 | ~520 – 1040 | Com 1–11 meses de passado, erro oscila mas permanece “moderado” |
| Virada de ano | **jan/2012** | **1612** (salto) | Modelo treinado só em 2011 **não generaliza** bem para 2012 |
| 2012 completo | mar – out/2012 | **1700 – 2243** | Mesmo com 400–640 dias de treino, erro **permanece alto** |
| Final | dez/2012 | 1437 | Leve melhora, mas ainda longe de 2011 |

**Insight principal:** **mais histórico não melhorou o modelo em 2012.** Isso indica **mudança de regime** entre anos (crescimento da rede, hábitos diferentes, clima/sazonalidade distinta) — comum em séries reais. Não significa que “dados demais atrapalham”; significa que **2011 sozinho não explica 2012**.

**Coluna `n_train`:** confirme a evolução — 31 dias em fev/2011, 365 em jan/2012, 700 em dez/2012. O histórico **cresce**, mas o erro em 2012 **não cai** proporcionalmente.

---

### Gráficos sugeridos (Excel ou similar)

1. **Filtro `mode = pipeline`** → gráfico de linhas: eixo X = `ref_date`, eixo Y = `mae` (ou `rmse`).
2. **Filtro `mode = walk_forward`** → mesmo gráfico; opcional: eixo secundário com `n_train`.
3. **Não sobrepor** os dois modos no mesmo eixo Y sem explicar a diferença metodológica.

Linha vertical em **2012-01-01** ajuda a marcar a virada de ano no walk-forward.

---

### O que concluir (e o que não concluir)

| Conclusão válida | Conclusão inválida |
|------------------|-------------------|
| A esteira mensal atual é **sensível ao mês** e usa **poucos dias** de treino | “Out/2012 teve o pior modelo; portanto out/2012 em produção será sempre ruim” |
| Prever 2012 só com padrões de 2011 **degrada** muito (walk-forward) | “RMSE pipeline 310 em jun/2012 prova que o modelo é excelente” |
| **MAE ~500–2000** em meses difíceis pode impactar planejamento de frota | Comparar pipeline de jan/2011 (RMSE 444) com walk-forward de jan/2012 (RMSE 1612) como se fossem a mesma métrica |
| Vale evoluir features (`holiday`, `weathersit`) e **retreino com janela móvel** | Este CSV substitui validação Athena/SFN em um `ref_date` específico |

---

### Traduzindo para decisões de negócio

| Métrica | Exemplo do CSV | Decisão prática |
|---------|----------------|-----------------|
| MAE = 350 | jul/2011 walk-forward | Erro médio ~350 bikes/dia — pode ser aceitável se a demanda diária for ~3000–5000 |
| MAE = 2000 | abr/2012 walk-forward | Erro ~2000 bikes/dia — **margem de segurança** na frota deve ser maior nesse perfil |
| RMSE >> MAE | vários meses | Dias com erro **muito grande** puxam RMSE — investigar outliers (feriados, clima extremo não modelado) |
| Salto em jan/2012 | walk-forward | Planejar **retreino anual** ou features que capturem tendência/crescimento, não só clima |

**Regra prática:** use **MAE** para explicar para negócio (“erramos X bikes por dia em média”). Use **tendência por modo** para priorizar melhorias (mais features, janela de treino, retreino ao mudar ano).

---

### Checklist rápido para o analista

1. Abrir `evolution_report.csv` e criar tabela dinâmica ou filtro por `mode`.
2. Calcular média/mediana de `mae` **dentro de cada modo** (não misturar).
3. Plotar evolução temporal; marcar 2012-01-01 no walk-forward.
4. Ler `n_train` / `n_eval` para entender **quantos dias** sustentam cada número.
5. Cruzar meses piores com calendário (feriados, clima) — lembrando que feriado/chuva **não estão** nas features hoje.
6. Para validar **um mês na AWS**, use Athena/`metrics.json` daquele `ref_date` — este CSV é visão **panorâmica** dos 24 meses.

### Gráficos automáticos (PNG + Excel)

Incluídos no Passo 9 via `plot_evolution_report.py`. Flags e troubleshooting: [Fase 1B — guia de testes](pipeline-testing-guide.md#fase-1b--teste-completo-do-modelo-local-24-meses).

```powershell
python scripts/plot_evolution_report.py
```

| Arquivo | Conteúdo |
|---------|----------|
| `evolution_report.png` | MAE/RMSE mês a mês (pipeline + walk-forward) |
| `evolution_report.xlsx` | Dados, gráficos por modo e aba Resumo |

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
