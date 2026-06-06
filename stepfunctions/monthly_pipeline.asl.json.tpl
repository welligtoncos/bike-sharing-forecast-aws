{
  "Comment": "Pipeline mensal Bike Sharing — S2 features → S3 treino/inferencia → S4 catalog/Athena. Legenda: prefixo Glue_* = AWS Glue Job; Athena_* = consulta SQL; numeros 00/01 = preparacao de ref_date.",
  "StartAt": "00_EscolherRefDate",
  "States": {
    "00_EscolherRefDate": {
      "Type": "Choice",
      "Comment": "[Prep] Usa ref_date do input manual (testes: 2011-06-01) ou calcula automaticamente no proximo estado.",
      "Choices": [
        {
          "Variable": "$.ref_date",
          "IsPresent": true,
          "Next": "01_MontarArgumentos"
        }
      ],
      "Default": "01A_RefDatePrimeiroDiaMes"
    },
    "01A_RefDatePrimeiroDiaMes": {
      "Type": "Pass",
      "Comment": "[Prep] ref_date = YYYY-MM-01 do mes em que a execucao iniciou (agendamento EventBridge dia 1).",
      "Parameters": {
        "ref_date.$": "States.Format('{}-{}-01', States.ArrayGetItem(States.StringSplit($$.Execution.StartTime, '-'), 0), States.ArrayGetItem(States.StringSplit($$.Execution.StartTime, '-'), 1))"
      },
      "Next": "01_MontarArgumentos"
    },
    "01_MontarArgumentos": {
      "Type": "Pass",
      "Comment": "[Prep] Consolida paths S3, database Athena, threshold RMSE e namespace CloudWatch para os jobs seguintes.",
      "Parameters": {
        "ref_date.$": "$.ref_date",
        "s3_input_path": "${s3_input_path}",
        "database_name": "${database_name}",
        "athena_workgroup": "${athena_workgroup_name}",
        "rmse_threshold": "${rmse_threshold}",
        "cloudwatch_namespace": "${cloudwatch_namespace}"
      },
      "Next": "Glue_S2_ValidarCSV_Features"
    },
    "Glue_S2_ValidarCSV_Features": {
      "Type": "Task",
      "Comment": "[S2 | Glue Job: validate-day-csv] Le raw/day.csv, valida colunas (season, temp, hum, windspeed, weekday, cnt), filtra pelo mes de ref_date e salva features/{ref_date}/features.parquet.",
      "Resource": "arn:aws:states:::glue:startJobRun.sync",
      "Parameters": {
        "JobName": "${glue_job_validate_day_csv_name}",
        "Arguments": {
          "--ref_date.$": "$.ref_date",
          "--s3_input_path.$": "$.s3_input_path"
        }
      },
      "ResultPath": null,
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "Alerta_SNS_Falha"
        }
      ],
      "Next": "Glue_S3_TreinarXGBoost"
    },
    "Glue_S3_TreinarXGBoost": {
      "Type": "Task",
      "Comment": "[S3-01/02 | Glue Job: train-xgboost] Treina XGBRegressor (split 80/20), grava metrics/{ref_date}/metrics.json, serializa models/{ref_date}/model.pkl e publica RMSE/MAE no CloudWatch (alarme se RMSE > threshold).",
      "Resource": "arn:aws:states:::glue:startJobRun.sync",
      "Parameters": {
        "JobName": "${glue_job_train_xgboost_name}",
        "Arguments": {
          "--ref_date.$": "$.ref_date",
          "--s3_input_path.$": "$.s3_input_path",
          "--rmse_threshold.$": "$.rmse_threshold",
          "--cloudwatch_namespace.$": "$.cloudwatch_namespace"
        }
      },
      "ResultPath": null,
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "Alerta_SNS_Falha"
        }
      ],
      "Next": "Glue_S3_InferirPredicoes"
    },
    "Glue_S3_InferirPredicoes": {
      "Type": "Task",
      "Comment": "[S3-03 | Glue Job: predict-xgboost] Carrega model.pkl, gera predicao para todos os dias do mes e grava predictions/ref_date={ref_date}/predictions.parquet (dteday, cnt_real, cnt_pred).",
      "Resource": "arn:aws:states:::glue:startJobRun.sync",
      "Parameters": {
        "JobName": "${glue_job_predict_xgboost_name}",
        "Arguments": {
          "--ref_date.$": "$.ref_date",
          "--s3_input_path.$": "$.s3_input_path"
        }
      },
      "ResultPath": null,
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "Alerta_SNS_Falha"
        }
      ],
      "Next": "Glue_S4_RegistrarGlueCatalog"
    },
    "Glue_S4_RegistrarGlueCatalog": {
      "Type": "Task",
      "Comment": "[S4-01 | Glue Job: register-predictions-catalog] Registra/atualiza tabela bike_sharing.predictions no Glue Catalog com particao ref_date (consulta Athena).",
      "Resource": "arn:aws:states:::glue:startJobRun.sync",
      "Parameters": {
        "JobName": "${glue_job_register_predictions_catalog_name}",
        "Arguments": {
          "--ref_date.$": "$.ref_date",
          "--s3_input_path.$": "$.s3_input_path",
          "--database_name.$": "$.database_name"
        }
      },
      "ResultPath": null,
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "Alerta_SNS_Falha"
        }
      ],
      "Next": "Prep_S4_MontarQueryAthena"
    },
    "Prep_S4_MontarQueryAthena": {
      "Type": "Pass",
      "Comment": "[S4-02 | Prep] Monta SQL: dteday, cnt_real, cnt_pred e abs_error = |real - pred| para o ref_date da execucao.",
      "Parameters": {
        "ref_date.$": "$.ref_date",
        "database_name.$": "$.database_name",
        "athena_workgroup.$": "$.athena_workgroup",
        "query_string.$": "States.Format('SELECT dteday, cnt_real, cnt_pred, ABS(cnt_real - cnt_pred) AS abs_error FROM ${database_name}.predictions WHERE ref_date = \\'{}\\' ORDER BY dteday ASC', $.ref_date)"
      },
      "Next": "Athena_S4_ValidarPredicoes"
    },
    "Athena_S4_ValidarPredicoes": {
      "Type": "Task",
      "Comment": "[S4-02 | Athena] Executa a query de validacao; resultados em s3://.../athena-results/. Fim do pipeline mensal.",
      "Resource": "arn:aws:states:::athena:startQueryExecution.sync",
      "Parameters": {
        "QueryString.$": "$.query_string",
        "WorkGroup.$": "$.athena_workgroup",
        "QueryExecutionContext": {
          "Database.$": "$.database_name"
        }
      },
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "Alerta_SNS_Falha"
        }
      ],
      "End": true
    },
    "Alerta_SNS_Falha": {
      "Type": "Task",
      "Comment": "[Alerta] Publica mensagem no topico SNS pipeline-alerts quando qualquer Glue Job ou Athena falha.",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "${sns_topic_arn}",
        "Subject": "[${name_prefix}] Pipeline mensal falhou",
        "Message.$": "States.Format('Pipeline mensal falhou. ref_date={} execucao={} error={} cause={}', $.ref_date, $$.Execution.Id, $.error.Error, $.error.Cause)"
      },
      "Next": "Falha_Pipeline"
    },
    "Falha_Pipeline": {
      "Type": "Fail",
      "Comment": "[Fim] Execucao marcada como FAILED apos alerta SNS.",
      "Error": "MonthlyPipelineFailed",
      "Cause": "Pipeline mensal nao concluiu com sucesso."
    }
  }
}
