output "s3_bucket_name" {
  value = aws_s3_bucket.datalake.id
}

output "glue_database_name" {
  value = aws_glue_catalog_database.ml_analytics.name
}

output "s3_endpoint" {
  value = "http://localhost:4566"
}

output "sagemaker_endpoint_name" {
  value = aws_sagemaker_endpoint.hybrid_fraud_endpoint.name
}

output "sns_alert_topic" {
  value = aws_sns_topic.fraud_alerts.arn
}

output "step_functions_arn" {
  value = aws_sfn_state_machine.mlops_pipeline.arn
}