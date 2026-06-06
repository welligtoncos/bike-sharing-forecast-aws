{
  "Comment": "S4-02 — Consulta Athena: predicoes do mes com erro absoluto (ref_date parametrizavel)",
  "StartAt": "BuildQuery",
  "States": {
    "BuildQuery": {
      "Type": "Pass",
      "Comment": "Monta QueryString com States.Format e ref_date do input da execucao",
      "Parameters": {
        "ref_date.$": "$.ref_date",
        "database_name": "${database_name}",
        "workgroup": "${athena_workgroup_name}",
        "query_string.$": "States.Format('SELECT dteday, cnt_real, cnt_pred, ABS(cnt_real - cnt_pred) AS abs_error FROM ${database_name}.predictions WHERE ref_date = \\'{}\\' ORDER BY dteday ASC', $.ref_date)"
      },
      "Next": "RunAthenaQuery"
    },
    "RunAthenaQuery": {
      "Type": "Task",
      "Comment": "Executa query e aguarda conclusao (startQueryExecution.sync)",
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
