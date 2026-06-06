{
  "Comment": "S4-03 — Treino XGBoost com rmse_threshold do input + alertas SNS em falha",
  "StartAt": "RunTrainXgboost",
  "States": {
    "RunTrainXgboost": {
      "Type": "Task",
      "Comment": "Publica RMSE/MAE no CloudWatch; RMSEThresholdBreached se rmse > threshold",
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
        "Subject": "[${name_prefix}] Glue train-xgboost falhou",
        "Message.$": "States.Format('Treino falhou. ref_date={} rmse_threshold={} error={} cause={}', $.ref_date, $.rmse_threshold, $.error.Error, $.error.Cause)"
      },
      "Next": "FailExecution"
    },
    "FailExecution": {
      "Type": "Fail",
      "Error": "TrainXgboostFailed",
      "Cause": "Glue Job train-xgboost nao concluiu com sucesso."
    }
  }
}
