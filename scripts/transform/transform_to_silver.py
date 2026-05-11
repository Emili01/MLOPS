import boto3
import pandas as pd
from io import StringIO
import os

ENDPOINT_URL = os.getenv('LOCALSTACK_ENDPOINT', 'http://localhost:4566')
BUCKET = os.getenv('S3_BUCKET', 'proyecto-ml-datalake')

s3 = boto3.client(
    's3',
    endpoint_url=ENDPOINT_URL,
    aws_access_key_id='test',
    aws_secret_access_key='test',
    region_name='us-east-1'
)

# Listar archivos en raw/ y tomar el más reciente
response = s3.list_objects_v2(Bucket=BUCKET, Prefix='raw/')
files = [obj for obj in response.get('Contents', []) if obj['Key'].endswith('.csv')]
latest_file = max(files, key=lambda x: x['LastModified'])

# Leer datos
obj = s3.get_object(Bucket=BUCKET, Key=latest_file['Key'])
df = pd.read_csv(obj['Body'])

# Transformaciones
for col in df.select_dtypes(include=['float64', 'int64']).columns:
    if col != 'target':
        df[f'{col}_normalized'] = (df[col] - df[col].mean()) / df[col].std()

# Guardar en Silver
csv_buffer = StringIO()
df.to_csv(csv_buffer, index=False)
s3.put_object(
    Bucket=BUCKET,
    Key='silver/training_data_normalized.csv',
    Body=csv_buffer.getvalue()
)

print(f"✅ Datos transformados y guardados en Silver layer")
print(f"📊 Columnas: {list(df.columns)}")
