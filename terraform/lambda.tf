data "archive_file" "lambda_zip" {
  type        = "zip"
  # CAMBIAR /src/ por /scripts/
  source_dir  = "${path.module}/../scripts/lambda" 
  output_path = "${path.module}/lambda_function.zip"
}

resource "aws_lambda_function" "fraud_trigger" {
  filename         = data.archive_file.lambda_zip.output_path
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