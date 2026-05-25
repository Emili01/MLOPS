resource "aws_sns_topic" "fraud_alerts" {
  name = "${var.project_name}-alerts"
}

resource "aws_sns_topic_subscription" "email_subscription" {
  topic_arn = aws_sns_topic.fraud_alerts.arn
  protocol  = "email"
  endpoint  = "example@gmail.com"
}

resource "aws_sqs_queue" "lambda_dlq" {
  name                      = "${var.project_name}-lambda-dlq"
  message_retention_seconds = 86400
}

resource "aws_cloudwatch_metric_alarm" "sagemaker_error_rate" {
  alarm_name          = "SageMaker-Endpoint-ErrorRate-High"
  alarm_description   = "Alerta critica: tasa de error del endpoint supera el 5%"
  namespace           = "AWS/SageMaker"
  metric_name         = "Invocation5XXErrors"
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 5
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
  EndpointName = "${var.project_name}-endpoint"
  VariantName  = "AllTraffic"
  }

  alarm_actions = [aws_sns_topic.fraud_alerts.arn]
  ok_actions    = [aws_sns_topic.fraud_alerts.arn]
}

resource "aws_cloudwatch_dashboard" "ml_dashboard" {
  dashboard_name = "proyecto-ml-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Widget 1: Duracion de Glue Jobs"
          view   = "timeSeries"
          region = "us-east-1"
          metrics = [
  	["AWS/Glue", "ResourceUsage", "Type", "Resource", "Resource", "Job", "Service", "Glue", "Class", "None"]
		]
          period = 300
          stat   = "Average"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Widget 2: Archivos en S3 Curated Zone"
          view   = "singleValue"
          region = "us-east-1"
          metrics = [
            ["AWS/S3", "NumberOfObjects", "BucketName", var.s3_bucket_name, "StorageType", "AllStorageTypes"]
          ]
          period = 86400
          stat   = "Average"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Widget 3: Tasa de Error en Endpoint SageMaker"
          view   = "timeSeries"
          region = "us-east-1"
          metrics = [
      ["AWS/SageMaker", "Invocation5XXErrors", "EndpointName", "${var.project_name}-endpoint", "VariantName", "AllTraffic"],
    ["AWS/SageMaker", "Invocations", "EndpointName", "${var.project_name}-endpoint", "VariantName", "AllTraffic"]
        ]
          period = 60
          stat   = "Sum"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Transacciones Exitosas vs Fallidas"
          view   = "timeSeries"
          region = "us-east-1"
          metrics = [
            ["MLOps/FraudDetection", "TransaccionesExitosas"],
            ["MLOps/FraudDetection", "TransaccionesFallidas"]
          ]
          period = 300
          stat   = "Sum"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6
        properties = {
          title  = "Tiempo de Inferencia SageMaker (ms)"
          view   = "timeSeries"
          region = "us-east-1"
          metrics = [
            ["MLOps/FraudDetection", "TiempoInferenciaSageMaker"]
          ]
          period = 300
          stat   = "Average"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 12
        width  = 12
        height = 6
        properties = {
          title  = "Tamano Promedio de Archivos Procesados (bytes)"
          view   = "timeSeries"
          region = "us-east-1"
          metrics = [
            ["MLOps/FraudDetection", "TamanoArchivoBytes"]
          ]
          period = 300
          stat   = "Average"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 18
        width  = 12
        height = 6
        properties = {
          title  = "Calidad de Datos"
          view   = "timeSeries"
          region = "us-east-1"
          metrics = [
            ["MLOps/FraudDetection", "CalidadDatos"],
            ["MLOps/FraudDetection", "ErroresCalidad"]
          ]
          period = 300
          stat   = "Average"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 18
        width  = 12
        height = 6
        properties = {
          title  = "Features Recibidos vs Valores Nulos"
          view   = "timeSeries"
          region = "us-east-1"
          metrics = [
            ["MLOps/FraudDetection", "FeaturesRecibidos"],
            ["MLOps/FraudDetection", "ValoresNulos"]
          ]
          period = 300
          stat   = "Average"
        }
      }
    ]
  })
}
