import boto3
import pandas as pd
from io import StringIO
from datetime import datetime
import os

ENDPOINT_URL = os.getenv('LOCALSTACK_ENDPOINT', 'http://localhost:4566')
BUCKET = os.getenv('S3_BUCKET', 'proyecto-ml-datalake')

s3 = boto3.client('s3', endpoint_url=ENDPOINT_URL,
                  aws_access_key_id='test',
                  aws_secret_access_key='test')

dataset_path = '../../datasets/creditcard.csv'
if not os.path.exists(dataset_path):
    print("❌ No se encuentra creditcard.csv en datasets/")
    print("Descárgalo primero: python scripts/eda/download_dataset.py")
    exit(1)

print(" Cargando dataset Credit Card Fraud Detection...")
df = pd.read_csv(dataset_path)
print(f"   {df.shape[0]:,} transacciones cargadas")

# Subir a Bronze layer (raw)
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
key = f'raw/creditcard_{timestamp}.csv'

csv_buffer = StringIO()
df.to_csv(csv_buffer, index=False)

s3.put_object(Bucket=BUCKET, Key=key, Body=csv_buffer.getvalue())

print(f"✅ Datos guardados en: s3://{BUCKET}/{key}")
print(f"{len(df):,} filas | {len(df.columns)} columnas")
