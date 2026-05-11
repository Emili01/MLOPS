variable "project_name" {
  description = "Nombre del proyecto MLOps"
  type        = string
  default     = "proyecto-ml"
}

variable "environment" {
  description = "Ambiente (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "s3_bucket_name" {
  description = "Nombre del bucket S3 del datalake"
  type        = string
  default     = "proyecto-ml-datalake"
}

variable "glue_database_name" {
  description = "Nombre de la base de datos en Glue"
  type        = string
  default     = "db_ml_analytics"
}