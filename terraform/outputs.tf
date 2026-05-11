output "s3_bucket_name" {
  value = aws_s3_bucket.datalake.id
}

output "glue_database_name" {
  value = aws_glue_catalog_database.ml_analytics.name
}

output "s3_endpoint" {
  value = "http://localhost:4566"
}