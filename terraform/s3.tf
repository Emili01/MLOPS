resource "aws_s3_bucket" "datalake" {
  bucket        = var.s3_bucket_name
  force_destroy = true 
}

# Crear carpetas base
resource "terraform_data" "create_s3_folders" {
  depends_on = [aws_s3_bucket.datalake]
  
  provisioner "local-exec" {
    command = <<-EOT
      awslocal s3api put-object --bucket ${var.s3_bucket_name} --key raw/
      awslocal s3api put-object --bucket ${var.s3_bucket_name} --key silver/
      awslocal s3api put-object --bucket ${var.s3_bucket_name} --key models/
      awslocal s3api put-object --bucket ${var.s3_bucket_name} --key inference_input/
      awslocal s3api put-object --bucket ${var.s3_bucket_name} --key scripts/
    EOT
  }
}

# Disparador para la Lambda de Inferencia
resource "aws_s3_bucket_notification" "bucket_notification" {
  bucket = aws_s3_bucket.datalake.id
  lambda_function {
    lambda_function_arn = aws_lambda_function.fraud_trigger.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "inference_input/" 
  }
  depends_on = [aws_lambda_permission.allow_s3]
}

# --- SUBIDA AUTOMÁTICA DE CÓDIGO ---

# 1. Subir el script de Glue (Fase A)
resource "aws_s3_object" "glue_script" {
  bucket = aws_s3_bucket.datalake.id
  key    = "scripts/transform_job.py"
  source = "${path.module}/../scripts/glue/transform_job.py"
  etag   = filemd5("${path.module}/../scripts/glue/transform_job.py")
}

# 2. Subir el código de SageMaker (Fase B)
resource "aws_s3_object" "sagemaker_code" {
  bucket = aws_s3_bucket.datalake.id
  key    = "scripts/sourcedir.tar.gz"
  source = "${path.module}/../scripts/sagemaker/sourcedir.tar.gz"
}

# 3. Subir el modelo falso (Para que inicie el Endpoint)
resource "aws_s3_object" "dummy_model" {
  bucket = aws_s3_bucket.datalake.id
  key    = "models/model.tar.gz"
  source = "${path.module}/../dummy_model.tar.gz"
}