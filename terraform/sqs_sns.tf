resource "aws_sns_topic" "fraud_alerts" {
  name = "${var.project_name}-alerts"
}

resource "aws_sqs_queue" "lambda_dlq" {
  name                      = "${var.project_name}-lambda-dlq"
  message_retention_seconds = 86400
}