import boto3
import uuid

ENDPOINT = "http://localhost:4566"
print("🔍 Iniciando prueba aislada de SageMaker en LocalStack (Con Credenciales)...")

# 1. Configuración impecable de Boto3 con credenciales dummy para LocalStack
sm = boto3.client("sagemaker", endpoint_url=ENDPOINT, region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test")
s3 = boto3.client("s3", endpoint_url=ENDPOINT, region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test")

# 2. Preparar el terreno en S3
bucket_name = "test-sagemaker-aislado"
try:
    s3.create_bucket(Bucket=bucket_name)
    # Metemos un archivo para que SageMaker no llore por "unsupported source" o carpeta vacía
    s3.put_object(Bucket=bucket_name, Key="data/train.csv", Body=b"col1,col2\n1,2")
    print(f"✅ Bucket '{bucket_name}' creado y datos de prueba inyectados.")
except Exception as e:
    print(f"⚠️ S3 devolvió una alerta (puede ser normal si el bucket ya existía): {e}")

# 3. La Invocación a SageMaker
job_name = f"test-aislado-{uuid.uuid4().hex[:8]}"
print(f"🚀 Lanzando SageMaker Training Job: {job_name}...")

try:
    response = sm.create_training_job(
        TrainingJobName=job_name,
        AlgorithmSpecification={
            'TrainingImage': '763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-training:2.0.0-cpu-py310',
            'TrainingInputMode': 'File'
        },
        RoleArn='arn:aws:iam::000000000000:role/proyecto-ml-sagemaker-role',
        InputDataConfig=[
            {
                "ChannelName": "train",
                "DataSource": {
                    "S3DataSource": {
                        "S3DataType": "S3Prefix",
                        "S3Uri": f"s3://{bucket_name}/data/",
                        "S3DataDistributionType": "FullyReplicated"
                    }
                }
            }
        ],
        OutputDataConfig={
            'S3OutputPath': f's3://{bucket_name}/output/'
        },
        ResourceConfig={
            'InstanceType': 'ml.m5.xlarge',
            'InstanceCount': 1,
            'VolumeSizeInGB': 10
        },
        StoppingCondition={
            'MaxRuntimeInSeconds': 3600
        }
    )
    
    print("\n" + "="*60)
    print("🏆 ¡SAGEMAKER ESTÁ VIVO Y ACEPTÓ EL TRABAJO!")
    print("="*60)
    print(f"Job ARN: {response.get('TrainingJobArn')}")

except Exception as e:
    print("\n" + "="*60)
    print("💀 EL NÚCLEO DE SAGEMAKER FALLÓ")
    print("="*60)
    print(str(e))