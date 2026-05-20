import boto3
import pandas as pd
from io import StringIO
from datetime import datetime
import os

BUCKET = os.getenv('S3_BUCKET', 'proyecto-ml-datalake-lalo-ug-2026') # <--- Tu nuevo nombre único

# Al no pasarle parámetros, boto3 usa mágicamente tus credenciales reales y la nube oficial
s3 = boto3.client('s3')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))  
DATASET_PATH = os.path.join(PROJECT_ROOT, 'datasets', 'creditcard.csv')

if not os.path.exists(DATASET_PATH):
    print(f"❌ No se encuentra creditcard.csv en {DATASET_PATH}")
    print("Descárgalo con el comando:")
    print("  python -c \"import urllib.request; urllib.request.urlretrieve('https://storage.googleapis.com/download.tensorflow.org/data/creditcard.csv', 'datasets/creditcard.csv')\"")
    exit(1)
  
print(" Cargando dataset Credit Card Fraud Detection...")
df = pd.read_csv(DATASET_PATH)
print(f"   {df.shape[0]:,} transacciones cargadas")

# Subir a Bronze layer (raw)
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
key = f'raw/creditcard_{timestamp}.csv'

csv_buffer = StringIO()
df.to_csv(csv_buffer, index=False)

s3.put_object(Bucket=BUCKET, Key=key, Body=csv_buffer.getvalue())

print(f"✅ Datos guardados en: s3://{BUCKET}/{key}")
print(f"{len(df):,} filas | {len(df.columns)} columnas")
