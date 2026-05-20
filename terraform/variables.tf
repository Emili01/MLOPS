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
  # Ponle un nombre único, por ejemplo:
  default     = "proyecto-ml-datalake-lalo-ug-2026" 
}

variable "glue_database_name" {
  description = "Nombre de la base de datos en Glue"
  type        = string
  default     = "db_ml_analytics"
}

#nuevo
variable "repackage_lambda_arn" {
  description = "ARN de la lambda que reempaqueta el modelo"
  default     = ""
}