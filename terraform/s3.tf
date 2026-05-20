resource "aws_s3_bucket" "datalake" {
  bucket        = var.s3_bucket_name
  force_destroy = true
}

# Carpetas base
resource "terraform_data" "create_s3_folders" {
  depends_on = [aws_s3_bucket.datalake]
  provisioner "local-exec" {
    command = <<-EOT
      aws s3api put-object --bucket ${var.s3_bucket_name} --key raw/
      aws s3api put-object --bucket ${var.s3_bucket_name} --key silver/
      aws s3api put-object --bucket ${var.s3_bucket_name} --key models/
      aws s3api put-object --bucket ${var.s3_bucket_name} --key inference_input/
      aws s3api put-object --bucket ${var.s3_bucket_name} --key scripts/
    EOT
  }
}

# Disparador Lambda
resource "aws_s3_bucket_notification" "bucket_notification" {
  bucket = aws_s3_bucket.datalake.id
  lambda_function {
    lambda_function_arn = aws_lambda_function.fraud_trigger.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "inference_input/"
  }
  depends_on = [aws_lambda_permission.allow_s3]
}

# --- SUBIDA DE CÓDIGO ---

# Script de Glue
resource "aws_s3_object" "glue_script" {
  bucket = aws_s3_bucket.datalake.id
  key    = "scripts/transform_job.py"
  source = "${path.module}/../scripts/glue/transform_job.py"
  etag   = filemd5("${path.module}/../scripts/glue/transform_job.py")
}

# Scripts de SageMaker sueltos (para el training job via canal code)
resource "aws_s3_object" "sagemaker_train_script" {
  bucket = aws_s3_bucket.datalake.id
  key    = "scripts/sagemaker/train_hybrid.py"
  source = "${path.module}/../scripts/sagemaker/train_hybrid.py"
  etag   = filemd5("${path.module}/../scripts/sagemaker/train_hybrid.py")
}

resource "aws_s3_object" "sagemaker_requirements" {
  bucket = aws_s3_bucket.datalake.id
  key    = "scripts/sagemaker/requirements.txt"
  source = "${path.module}/../scripts/sagemaker/requirements.txt"
  etag   = filemd5("${path.module}/../scripts/sagemaker/requirements.txt")
}

# sourcedir.tar.gz para el endpoint de inferencia
resource "aws_s3_object" "sagemaker_sourcedir" {
  bucket      = aws_s3_bucket.datalake.id
  key         = "scripts/sourcedir.tar.gz"
  source      = "${path.module}/../sourcedir.tar.gz"
  etag        = filemd5("${path.module}/../sourcedir.tar.gz")
}

# Modelo dummy para endpoint inicial
resource "aws_s3_object" "dummy_model" {
  bucket = aws_s3_bucket.datalake.id
  key    = "models/model.tar.gz"
  source = "${path.module}/../dummy_model.tar.gz"
}

# Dataset raw
resource "aws_s3_object" "raw_dataset" {
  bucket = aws_s3_bucket.datalake.id
  key    = "raw/creditcard.csv"
  source = "${path.module}/../datasets/creditcard.csv"
  etag   = filemd5("${path.module}/../datasets/creditcard.csv")
}

#nuevo
resource "aws_s3_object" "sagemaker_inference_script" {
  bucket = aws_s3_bucket.datalake.id
  key    = "scripts/sagemaker/inference.py"
  source = "${path.module}/../scripts/sagemaker/inference.py"
  etag   = filemd5("${path.module}/../scripts/sagemaker/inference.py")
}