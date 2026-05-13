# Despliegue del Modelo Híbrido en SageMaker
resource "aws_sagemaker_model" "hybrid_model" {
  name               = "${var.project_name}-model"
  execution_role_arn = aws_iam_role.sagemaker_role.arn

  # --- CRUCIAL: Esperar a que Terraform suba los archivos a S3 primero ---
  depends_on = [
    aws_s3_object.sagemaker_code,
    aws_s3_object.dummy_model
  ]

  primary_container {
    # Imagen oficial de PyTorch para inferencia en AWS
    image          = "763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-inference:2.0.0-cpu-py310"
    
    # Ruta donde estará el modelo final (o el dummy al inicio)
    model_data_url = "s3://${aws_s3_bucket.datalake.id}/models/model.tar.gz"
    
    environment = {
      SAGEMAKER_PROGRAM          = "inference.py"
      SAGEMAKER_SUBMIT_DIRECTORY = "s3://${aws_s3_bucket.datalake.id}/scripts/sourcedir.tar.gz"
    }
  }
}

# Configuración del Hardware del Endpoint
resource "aws_sagemaker_endpoint_configuration" "endpoint_config" {
  name = "${var.project_name}-endpoint-config"
  
  production_variants {
    variant_name           = "AllTraffic"
    model_name             = aws_sagemaker_model.hybrid_model.name
    initial_instance_count = 1
    instance_type          = "ml.t2.medium" # Instancia económica para CPU
  }
}

# Despliegue del Endpoint físico
resource "aws_sagemaker_endpoint" "hybrid_fraud_endpoint" {
  name                 = "${var.project_name}-endpoint"
  endpoint_config_name = aws_sagemaker_endpoint_configuration.endpoint_config.name
}