import boto3
import pandas as pd
from io import StringIO
from datetime import datetime
import os

# Configuración desde variables de entorno o defaults
ENDPOINT_URL = os.getenv('LOCALSTACK_ENDPOINT', 'http://localhost:4566')
BUCKET = os.getenv('S3_BUCKET', 'proyecto-ml-datalake')

s3 = boto3.client(
    's3',
    endpoint_url=ENDPOINT_URL,
    aws_access_key_id='test',
    aws_secret_access_key='test',
    region_name='us-east-1'
)

# Cargar datos de ejemplo o crear si no existe
csv_path = '../datasets/sample_data.csv'
if os.path.exists(csv_path):
    df = pd.read_csv(csv_path)
else:
    # Datos de ejemplo
    df = pd.DataFrame({
        'feature1': [1.2, 2.3, 3.1, 4.5, 5.0],
        'feature2': [0.5, 1.5, 2.5, 3.5, 4.5],
        'target': [0, 1, 0, 1, 1]
    })
    os.makedirs('../datasets', exist_ok=True)
    df.to_csv(csv_path, index=False)

# Guardar en Bronze layer
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
csv_buffer = StringIO()
df.to_csv(csv_buffer, index=False)

s3.put_object(
    Bucket=BUCKET,
    Key=f'raw/training_data_{timestamp}.csv',
    Body=csv_buffer.getvalue()
)

print(f"✅ Datos guardados en: raw/training_data_{timestamp}.csv")
