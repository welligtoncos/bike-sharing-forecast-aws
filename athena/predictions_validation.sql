-- S4-02 — Validacao de predicoes no Athena
-- Parametro: ref_date (particao Hive, ex.: 2011-06-01)
-- Substituir :ref_date ou usar Step Functions validate_predictions (BuildQuery + RunAthenaQuery)

SELECT
    dteday,
    cnt_real,
    cnt_pred,
    ABS(cnt_real - cnt_pred) AS abs_error
FROM bike_sharing.predictions
WHERE ref_date = '2011-06-01'  -- parametrizar: ref_date via Step Functions input
ORDER BY dteday ASC;
