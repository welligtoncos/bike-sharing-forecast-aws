# =============================================================================
# S4-01 — Glue Catalog + Lake Formation (database bike_sharing)
# =============================================================================
#
# Database Glue bike_sharing e job que registra tabela predictions particionada
# por ref_date, com schema inferido do Parquet (dteday, cnt_real, cnt_pred).
#
# Layout S3:
#   s3://{bucket}/predictions/ref_date={ref_date}/predictions.parquet
# =============================================================================

resource "aws_glue_catalog_database" "bike_sharing" {
  name         = var.glue_predictions_db_name
  description  = "Bike Sharing pipeline — predições e consultas Athena"
  location_uri = "s3://${aws_s3_bucket.pipeline.id}/predictions/"

  tags = {
    Name = var.glue_predictions_db_name
  }
}

# Lake Formation — opcional (contas sem lakeformation:GrantPermissions).
resource "aws_lakeformation_resource" "pipeline" {
  count = var.enable_lake_formation ? 1 : 0
  arn   = aws_s3_bucket.pipeline.arn
}

resource "aws_lakeformation_permissions" "glue_bike_sharing_db" {
  count     = var.enable_lake_formation ? 1 : 0
  principal = aws_iam_role.glue.arn

  permissions = ["CREATE_TABLE", "ALTER", "DROP", "DESCRIBE"]

  database {
    name = aws_glue_catalog_database.bike_sharing.name
  }
}

resource "aws_lakeformation_permissions" "glue_bike_sharing_data_location" {
  count     = var.enable_lake_formation ? 1 : 0
  principal = aws_iam_role.glue.arn

  permissions = ["DATA_LOCATION_ACCESS"]

  data_location {
    arn = aws_s3_bucket.pipeline.arn
  }
}

resource "aws_s3_object" "glue_module_catalog_predictions" {
  bucket = aws_s3_bucket.pipeline.id
  key    = local.glue_module_catalog_predictions_key
  source = "${path.module}/scripts/glue_catalog_predictions.py"
  etag   = filemd5("${path.module}/scripts/glue_catalog_predictions.py")

  tags = {
    Name = local.glue_module_catalog_predictions_key
  }
}

resource "aws_s3_object" "glue_script_register_predictions_catalog" {
  bucket = aws_s3_bucket.pipeline.id
  key    = local.glue_script_register_predictions_catalog_key
  source = "${path.module}/scripts/register_predictions_catalog_job.py"
  etag   = filemd5("${path.module}/scripts/register_predictions_catalog_job.py")

  tags = {
    Name = local.glue_script_register_predictions_catalog_key
  }
}

resource "aws_glue_job" "register_predictions_catalog" {
  name         = local.glue_job_register_predictions_catalog_name
  role_arn     = aws_iam_role.glue.arn
  glue_version = "3.0"
  max_capacity = 0.0625
  timeout      = 10
  max_retries  = 0

  command {
    name            = "pythonshell"
    script_location = "s3://${aws_s3_bucket.pipeline.id}/${local.glue_script_register_predictions_catalog_key}"
    python_version  = "3.9"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--enable-continuous-cloudwatch-log" = "true"
    "--extra-py-files"                   = "s3://${aws_s3_bucket.pipeline.id}/${local.glue_module_catalog_predictions_key}"
    "--additional-python-modules"        = "s3fs,pyarrow"
    "--s3_input_path"                    = local.s3_input_day_csv_path
    "--ref_date"                         = "1970-01-01"
    "--database_name"                    = var.glue_predictions_db_name
  }

  tags = {
    Name = local.glue_job_register_predictions_catalog_name
  }

  depends_on = [
    aws_glue_catalog_database.bike_sharing,
    aws_s3_object.glue_module_catalog_predictions,
    aws_s3_object.glue_script_register_predictions_catalog,
    aws_iam_role_policy_attachment.glue_service,
    aws_iam_role_policy.glue_s3,
    aws_iam_role_policy.glue_catalog,
    aws_iam_role_policy.glue_catalog_write,
    aws_iam_role_policy.glue_logs,
  ]
}
