# Zip para la Lambda de inferencia (handler.py + train_trigger.py)
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../scripts/lambda"
  output_path = "${path.module}/lambda_function.zip"
}

# Zip para la Lambda de reempaquetado (solo repackage_model.py)
data "archive_file" "repackage_zip" {
  type        = "zip"
  source_file = "${path.module}/../scripts/lambda/repackage_model.py"
  output_path = "${path.module}/repackage_lambda.zip"
}

# Lambda de inferencia (disparada por S3)
resource "aws_lambda_function" "fraud_trigger" {
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  function_name    = "${var.project_name}-trigger"
  role             = aws_iam_role.lambda_role.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.10"
  timeout          = 30

  dead_letter_config {
    target_arn = aws_sqs_queue.lambda_dlq.arn
  }

  environment {
    variables = {
      SAGEMAKER_ENDPOINT = aws_sagemaker_endpoint.hybrid_fraud_endpoint.name
      SNS_TOPIC_ARN      = aws_sns_topic.fraud_alerts.arn
    }
  }
}

resource "aws_lambda_permission" "allow_s3" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.fraud_trigger.arn
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.datalake.arn
}

# Lambda de reempaquetado (invocada por Step Functions)
resource "aws_lambda_function" "repackage_model" {
  filename         = data.archive_file.repackage_zip.output_path
  source_code_hash = data.archive_file.repackage_zip.output_base64sha256
  function_name    = "${var.project_name}-repackage-model"
  role             = aws_iam_role.lambda_role.arn
  handler          = "repackage_model.lambda_handler"
  runtime          = "python3.10"
  timeout          = 300
  memory_size      = 512

  environment {
    variables = {
      BUCKET         = aws_s3_bucket.datalake.bucket
      SAGEMAKER_ROLE = aws_iam_role.sagemaker_role.arn
    }
  }
}