{
  "Comment": "S4-02 — Validacao analitica via Athena. Legenda: Prep_* prepara SQL; Athena_* executa consulta.",
  "StartAt": "Prep_S4_MontarQueryValidacao",
  "States": {
    "Prep_S4_MontarQueryValidacao": {
      "Type": "Pass",
      "Comment": "[S4-02 | Prep] Monta SQL com ref_date do input: compara cnt_real vs cnt_pred e calcula abs_error por dia.",
      "Parameters": {
        "ref_date.$": "$.ref_date",
        "database_name": "${database_name}",
        "workgroup": "${athena_workgroup_name}",
        "query_string.$": "States.Format('SELECT dteday, cnt_real, cnt_pred, ABS(cnt_real - cnt_pred) AS abs_error FROM ${database_name}.predictions WHERE ref_date = \\'{}\\' ORDER BY dteday ASC', $.ref_date)"
      },
      "Next": "Athena_S4_ExecutarValidacao"
    },
    "Athena_S4_ExecutarValidacao": {
      "Type": "Task",
      "Comment": "[S4-02 | Athena] Roda query no workgroup glue-b3-dev-athena-pipeline; resultado em athena-results/ no bucket do pipeline.",
      "Resource": "arn:aws:states:::athena:startQueryExecution.sync",
      "Parameters": {
        "QueryString.$": "$.query_string",
        "WorkGroup.$": "$.workgroup",
        "QueryExecutionContext": {
          "Database.$": "$.database_name"
        }
      },
      "End": true
    }
  }
}
