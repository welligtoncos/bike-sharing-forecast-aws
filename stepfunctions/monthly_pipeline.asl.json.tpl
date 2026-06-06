{
  "Comment": "Pipeline mensal completo: features → treino → inferencia → catalog → Athena (S2-S4)",
  "StartAt": "ResolveRefDate",
  "States": {
    "ResolveRefDate": {
      "Type": "Choice",
      "Comment": "Input manual pode informar ref_date (ex.: 2011-06-01 para testes)",
      "Choices": [
        {
          "Variable": "$.ref_date",
          "IsPresent": true,
          "Next": "BuildArguments"
        }
      ],
      "Default": "SetRefDateFromClock"
    },
    "SetRefDateFromClock": {
      "Type": "Pass",
      "Comment": "ref_date = primeiro dia do mes corrente (YYYY-MM-01)",
      "Parameters": {
        "ref_date.$": "States.Format('{}-{}-01', States.ArrayGetItem(States.StringSplit($$.Execution.StartTime, '-'), 0), States.ArrayGetItem(States.StringSplit($$.Execution.StartTime, '-'), 1))"
      },
      "Next": "BuildArguments"
    },
    "BuildArguments": {
      "Type": "Pass",
      "Parameters": {
        "ref_date.$": "$.ref_date",
        "s3_input_path": "${s3_input_path}",
        "database_name": "${database_name}",
        "athena_workgroup": "${athena_workgroup_name}",
        "rmse_threshold": "${rmse_threshold}",
        "cloudwatch_namespace": "${cloudwatch_namespace}"
      },
      "Next": "RunValidateFeatures"
    },
    "RunValidateFeatures": {
      "Type": "Task",
      "Comment": "S2 — validate_day_csv → features.parquet",
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
          "Next": "NotifyFailure"
        }
      ],
      "Next": "RunTrainXgboost"
    },
    "RunTrainXgboost": {
      "Type": "Task",
      "Comment": "S3 — treino XGBoost + model.pkl + metricas CloudWatch",
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
          "Next": "NotifyFailure"
        }
      ],
      "Next": "RunPredictXgboost"
    },
    "RunPredictXgboost": {
      "Type": "Task",
      "Comment": "S3-03 — inferencia → predictions.parquet",
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
          "Next": "NotifyFailure"
        }
      ],
      "Next": "RunRegisterCatalog"
    },
    "RunRegisterCatalog": {
      "Type": "Task",
      "Comment": "S4-01 — Glue Catalog bike_sharing.predictions",
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
          "Next": "NotifyFailure"
        }
      ],
      "Next": "BuildAthenaQuery"
    },
    "BuildAthenaQuery": {
      "Type": "Pass",
      "Comment": "S4-02 — SQL validacao predicoes",
      "Parameters": {
        "ref_date.$": "$.ref_date",
        "database_name.$": "$.database_name",
        "athena_workgroup.$": "$.athena_workgroup",
        "query_string.$": "States.Format('SELECT dteday, cnt_real, cnt_pred, ABS(cnt_real - cnt_pred) AS abs_error FROM ${database_name}.predictions WHERE ref_date = \\'{}\\' ORDER BY dteday ASC', $.ref_date)"
      },
      "Next": "RunAthenaQuery"
    },
    "RunAthenaQuery": {
      "Type": "Task",
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
          "Next": "NotifyFailure"
        }
      ],
      "End": true
    },
    "NotifyFailure": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "${sns_topic_arn}",
        "Subject": "[${name_prefix}] Pipeline mensal falhou",
        "Message.$": "States.Format('Pipeline mensal falhou. ref_date={} execucao={} error={} cause={}', $.ref_date, $$.Execution.Id, $.error.Error, $.error.Cause)"
      },
      "Next": "FailExecution"
    },
    "FailExecution": {
      "Type": "Fail",
      "Error": "MonthlyPipelineFailed",
      "Cause": "Pipeline mensal nao concluiu com sucesso."
    }
  }
}
