{
  "Comment": "S4-03 — Treino + inferencia com rmse_threshold no input. Legenda: Glue_S3_* = jobs Python Shell no AWS Glue.",
  "StartAt": "Glue_S3_Treinar_ComObservabilidade",
  "States": {
    "Glue_S3_Treinar_ComObservabilidade": {
      "Type": "Task",
      "Comment": "[S3 + S4-03 | Glue Job: train-xgboost] Treina XGBoost, salva model.pkl e metrics.json, publica RMSE/MAE no CloudWatch. Se RMSE > rmse_threshold (input JSON), dispara metrica RMSEThresholdBreached para alarme SNS.",
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
          "Next": "Alerta_SNS_Falha"
        }
      ],
      "Next": "Glue_S3_InferirPredicoes"
    },
    "Glue_S3_InferirPredicoes": {
      "Type": "Task",
      "Comment": "[S3-03 | Glue Job: predict-xgboost] Usa model.pkl treinado no passo anterior e grava predictions/ref_date={ref_date}/predictions.parquet no S3.",
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
          "Next": "Alerta_SNS_Falha"
        }
      ],
      "End": true
    },
    "Alerta_SNS_Falha": {
      "Type": "Task",
      "Comment": "[Alerta] Notifica falha de treino ou inferencia via SNS.",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "${sns_topic_arn}",
        "Subject": "[${name_prefix}] Glue train/predict falhou",
        "Message.$": "States.Format('Treino/inferencia falhou. ref_date={} rmse_threshold={} error={} cause={}', $.ref_date, $.rmse_threshold, $.error.Error, $.error.Cause)"
      },
      "Next": "Falha_TreinoInferencia"
    },
    "Falha_TreinoInferencia": {
      "Type": "Fail",
      "Comment": "[Fim] Execucao FAILED.",
      "Error": "TrainPredictFailed",
      "Cause": "Glue Job train-xgboost ou predict-xgboost nao concluiu com sucesso."
    }
  }
}
