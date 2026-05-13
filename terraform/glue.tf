resource "aws_glue_catalog_database" "ml_analytics" {
  name = var.glue_database_name
}

resource "aws_glue_crawler" "training_data" {
  database_name = aws_glue_catalog_database.ml_analytics.name
  name          = "${var.project_name}-training-crawler"
  role          = aws_iam_role.glue_crawler.arn

  s3_target {
    path = "s3://${aws_s3_bucket.datalake.id}/raw/"
  }

  schema_change_policy {
    delete_behavior = "LOG"
    update_behavior = "UPDATE_IN_DATABASE"
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Tables = {
        AddOrUpdateBehavior = "MergeNewColumns"
      }
    }
  })
}

# --- NUEVO: EL MOTOR DE PROCESAMIENTO (FASE A) ---
resource "aws_glue_job" "preprocessing_job" {
  name     = "fase-a-preprocessing-job"
  role_arn = aws_iam_role.glue_crawler.arn

  command {
    name            = "glueetl" 
    script_location = "s3://${aws_s3_bucket.datalake.id}/scripts/transform_job.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language" = "python"
    "--TempDir"      = "s3://${aws_s3_bucket.datalake.id}/temp/"
  }

  glue_version      = "3.0"
  worker_type       = "G.1X"
  number_of_workers = 2
}