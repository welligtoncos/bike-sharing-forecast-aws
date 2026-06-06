{
  "Comment": "S4-03 — Treino + inferencia com rmse_threshold parametrizavel",
  "StartAt": "RunTrainXgboost",
  "States": {
    "RunTrainXgboost": {
      "Type": "Task",
      "Comment": "Publica RMSE/MAE no CloudWatch; salva model.pkl",
      "Resource": "arn:aws:states:::glue:startJobRun.sync",
      "Parameters": {
        "JobName": "${glue_job_train_xgboost_name}",
        "Arguments": {
          "--ref_date.$": "$.ref_date",
          "--s3_input_path": "${s3_input_path}",
          "--rmse_threshold.$": "States.Format('{}', $.rmse_threshold)",
          "--cloudwatch_namespace": "${cloudwatch_namespace}"
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
      "Comment": "S3-03 — predictions.parquet a partir de model.pkl",
      "Resource": "arn:aws:states:::glue:startJobRun.sync",
      "Parameters": {
        "JobName": "${glue_job_predict_xgboost_name}",
        "Arguments": {
          "--ref_date.$": "$.ref_date",
          "--s3_input_path": "${s3_input_path}"
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
        "Subject": "[${name_prefix}] Glue train/predict falhou",
        "Message.$": "States.Format('Treino/inferencia falhou. ref_date={} rmse_threshold={} error={} cause={}', $.ref_date, $.rmse_threshold, $.error.Error, $.error.Cause)"
      },
      "Next": "FailExecution"
    },
    "FailExecution": {
      "Type": "Fail",
      "Error": "TrainPredictFailed",
      "Cause": "Glue Job train-xgboost ou predict-xgboost nao concluiu com sucesso."
    }
  }
}
