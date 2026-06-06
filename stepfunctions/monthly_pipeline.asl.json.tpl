{
  "Comment": "S1-03 - Dispara Glue Job mensalmente com ref_date (1o dia do mes) e s3_input_path raw/day.csv",
  "StartAt": "BuildArguments",
  "States": {
    "BuildArguments": {
      "Type": "Pass",
      "Comment": "ref_date = primeiro dia do mes corrente (YYYY-MM-01) derivado de $$.Execution.StartTime",
      "Parameters": {
        "ref_date.$": "States.Format('{}-{}-01', States.ArrayGetItem(States.StringSplit($$.Execution.StartTime, '-'), 0), States.ArrayGetItem(States.StringSplit($$.Execution.StartTime, '-'), 1))",
        "s3_input_path": "${s3_input_path}",
        "glue_job_name": "${glue_job_name}"
      },
      "Next": "RunGlueJob"
    },
    "RunGlueJob": {
      "Type": "Task",
      "Comment": "Invoca Glue Job e aguarda conclusao (startJobRun.sync)",
      "Resource": "arn:aws:states:::glue:startJobRun.sync",
      "Parameters": {
        "JobName.$": "$.glue_job_name",
        "Arguments": {
          "--ref_date.$": "$.ref_date",
          "--s3_input_path.$": "$.s3_input_path"
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
      "Comment": "Publica alerta SNS quando o Glue Job falha",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "${sns_topic_arn}",
        "Subject": "[${name_prefix}] Glue Job mensal falhou",
        "Message.$": "States.Format('Pipeline mensal falhou. ref_date={} s3_input_path={} execucao={} error={} cause={}', $.ref_date, $.s3_input_path, $$.Execution.Id, $.error.Error, $.error.Cause)"
      },
      "Next": "FailExecution"
    },
    "FailExecution": {
      "Type": "Fail",
      "Error": "GlueJobFailed",
      "Cause": "Glue Job do pipeline mensal nao concluiu com sucesso."
    }
  }
}
