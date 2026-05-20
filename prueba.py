import boto3, json
import pandas as pd

# ACTUALIZADO: Leer el archivo local descargado
df = pd.read_parquet('./sample.parquet')

cols_to_drop = ['processed_at', 'source', 'version', 'Time', 'Amount', 'Class']
df_clean = df.drop(columns=[c for c in cols_to_drop if c in df.columns])

# ¡LA CLAVE ESTÁ AQUÍ! Usar to_dict() preserva los nombres de las columnas
fila_normal = df_clean.iloc[0].to_dict()
fila_fraude = df_clean.iloc[1].to_dict()  
fila_2 = df_clean.iloc[2].to_dict()
fila_3 = df_clean.iloc[3].to_dict()
fila_4 = df_clean.iloc[4].to_dict()

print(f"Features en el diccionario: {len(fila_normal)}")

runtime = boto3.client('sagemaker-runtime', region_name='us-east-1')
ENDPOINT = 'proyecto-ml-endpoint'

casos = [
    ("fila_real_0",   fila_normal),
    ("fila_real_1",   fila_fraude),
    ("fila_real_2",   fila_2),
    ("fila_real_3",   fila_3),
    ("fila_real_4",   fila_4),
]

print("=" * 62)
print(f"{'#':>3}  {'Tipo':<20}  {'Fraude':>8}  {'Prob':>8}")
print("=" * 62)

for i, (tipo, features) in enumerate(casos):
    try:
        # Se manda directamente el diccionario, no una lista de listas
        payload = json.dumps(features).encode('utf-8')
        response = runtime.invoke_endpoint(
            EndpointName=ENDPOINT,
            ContentType='application/json',
            Accept='application/json',
            Body=payload
        )
        result   = json.loads(response['Body'].read())
        is_fraud = result.get('is_fraud', '?')
        prob     = result.get('fraud_probability', 0)
        flag     = '🚨' if is_fraud else '✅'
        print(f"{i+1:>3}  {tipo:<20}  {flag} {str(is_fraud):>5}  {prob:>8.4f}")
    except Exception as e:
        print(f"{i+1:>3}  {tipo:<20}  ERROR: {e}")

print("=" * 62)