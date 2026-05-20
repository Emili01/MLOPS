import boto3
import tarfile
import os
import tempfile

s3 = boto3.client('s3')
sm = boto3.client('sagemaker')

BUCKET = os.environ['BUCKET']
INFERENCE_SCRIPT_KEY = 'scripts/sagemaker/inference.py'
ROLE = os.environ['SAGEMAKER_ROLE']
IMAGE = '763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-inference:2.0.0-cpu-py310'

def lambda_handler(event, context):
    model_s3_uri = event['model_s3_uri']
    # s3://bucket/models/job/output/model.tar.gz
    model_key = model_s3_uri.replace(f's3://{BUCKET}/', '')

    with tempfile.TemporaryDirectory() as tmpdir:
        # Descargar model.tar.gz original
        model_path = os.path.join(tmpdir, 'model.tar.gz')
        s3.download_file(BUCKET, model_key, model_path)

        # Extraer
        extract_dir = os.path.join(tmpdir, 'model')
        os.makedirs(extract_dir)
        with tarfile.open(model_path, 'r:gz') as tar:
            tar.extractall(extract_dir)

        # Descargar inference.py y agregarlo
        inference_path = os.path.join(extract_dir, 'inference.py')
        s3.download_file(BUCKET, INFERENCE_SCRIPT_KEY, inference_path)

        # Reempaquetar
        fixed_path = os.path.join(tmpdir, 'model_fixed.tar.gz')
        with tarfile.open(fixed_path, 'w:gz') as tar:
            for fname in os.listdir(extract_dir):
                tar.add(os.path.join(extract_dir, fname), arcname=fname)

        # Subir a ruta fija
        fixed_key = 'models/fixed/model.tar.gz'
        s3.upload_file(fixed_path, BUCKET, fixed_key)

    return {
        'fixed_model_uri': f's3://{BUCKET}/{fixed_key}',
        'role': ROLE,
        'image': IMAGE
    }