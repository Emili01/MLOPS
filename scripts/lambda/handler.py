import os
import io
import json
import time
import boto3
import csv
import pandas as pd

s3_client = boto3.client('s3')
sagemaker_client = boto3.client('sagemaker-runtime')
sns_client = boto3.client('sns')
cloudwatch_client = boto3.client('cloudwatch')

ENDPOINT_NAME = os.environ['SAGEMAKER_ENDPOINT']
SNS_TOPIC = os.environ['SNS_TOPIC_ARN']
COLS_TO_DROP = ['processed_at', 'source', 'version', 'Time', 'Amount', 'Class']

def publish_metric(name, value, unit='Count'):
    cloudwatch_client.put_metric_data(
        Namespace='MLOps/FraudDetection',
        MetricData=[{
            'MetricName': name,
            'Value': value,
            'Unit': unit
        }]
    )

def check_data_quality(transaction_data):
    expected_features = 64
    total_features = len(transaction_data)
    null_count = sum(1 for v in transaction_data.values() if v is None)

    publish_metric('FeaturesRecibidos', total_features, 'Count')
    publish_metric('ValoresNulos', null_count, 'Count')

    is_valid = total_features == expected_features and null_count == 0
    publish_metric('CalidadDatos', 1 if is_valid else 0, 'Count')

    if not is_valid:
        publish_metric('ErroresCalidad', 1, 'Count')

    return is_valid

def lambda_handler(event, context):
    try:
        record = event['Records'][0]
        bucket_name = record['s3']['bucket']['name']
        file_key = record['s3']['object']['key']
        file_size = record['s3']['object'].get('size', 0)

        print(f"Procesando archivo: s3://{bucket_name}/{file_key}")

        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        raw_bytes = response['Body'].read()

        transaction_data = {}

        if file_key.lower().endswith('.parquet'):
            df = pd.read_parquet(io.BytesIO(raw_bytes))
            df = df.drop(columns=[c for c in COLS_TO_DROP if c in df.columns])
            transaction_data = df.iloc[0].to_dict()

        elif file_key.lower().endswith('.json'):
            transaction_data = json.loads(raw_bytes.decode('utf-8'))

        elif file_key.lower().endswith('.csv'):
            file_content = raw_bytes.decode('utf-8')
            csv_reader = csv.DictReader(file_content.splitlines())
            transaction_data = next(csv_reader)
            for key, value in transaction_data.items():
                try:
                    transaction_data[key] = float(value)
                except ValueError:
                    pass
        else:
            raise ValueError(
                f"Formato no soportado: {file_key}. "
                f"Formatos válidos: .parquet, .json, .csv"
            )

        print(f"Payload listo. Features: {len(transaction_data)}")

        # Verificar calidad de datos
        calidad_ok = check_data_quality(transaction_data)
        if not calidad_ok:
            print(f"Advertencia de calidad: features={len(transaction_data)}, esperados=64")

        print("Enviando payload a SageMaker...")

        # Medir tiempo de inferencia
        inicio = time.time()
        sm_response = sagemaker_client.invoke_endpoint(
            EndpointName=ENDPOINT_NAME,
            ContentType='application/json',
            Accept='application/json',
            Body=json.dumps(transaction_data)
        )
        tiempo_inferencia = (time.time() - inicio) * 1000

        result = json.loads(sm_response['Body'].read().decode('utf-8'))
        is_fraud = result.get('is_fraud', False)
        fraud_probability = result.get('fraud_probability', 0.0)

        print(f"Inferencia completada. ¿Es fraude?: {is_fraud} | Probabilidad: {fraud_probability:.4f} | Tiempo: {tiempo_inferencia:.0f}ms")

        # Publicar métricas de negocio en CloudWatch
        publish_metric('TransaccionesExitosas', 1)
        publish_metric('TamanoArchivoBytes', file_size, 'Bytes')
        publish_metric('TiempoInferenciaSageMaker', tiempo_inferencia, 'Milliseconds')
        if is_fraud:
            publish_metric('FraudesDetectados', 1)

        if is_fraud:
            subject = "🚨 ALERTA CRÍTICA — Fraude Detectado"
            mensaje = (
                f"🚨 ¡ALERTA CRÍTICA DE FRAUDE! 🚨\n\n"
                f"Se ha detectado una transacción anómala.\n"
                f"Archivo origen: s3://{bucket_name}/{file_key}\n"
                f"Probabilidad calculada por XGBoost: {fraud_probability:.4f}\n"
                f"Tiempo de inferencia: {tiempo_inferencia:.0f}ms\n"
                f"Acción requerida: Revisión inmediata."
            )
        else:
            subject = "✅ Transacción Procesada — Sin Fraude"
            mensaje = (
                f"Transacción analizada correctamente.\n\n"
                f"Archivo: s3://{bucket_name}/{file_key}\n"
                f"¿Es fraude?: {is_fraud}\n"
                f"Probabilidad: {fraud_probability:.4f}\n"
                f"Tiempo de inferencia: {tiempo_inferencia:.0f}ms\n"
                f"Estado: Transacción legítima."
            )

        sns_client.publish(
            TopicArn=SNS_TOPIC,
            Message=mensaje,
            Subject=subject
        )
        print(f"Notificación enviada vía SNS. Asunto: {subject}")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Transacción procesada correctamente",
                "file": file_key,
                "prediction": result,
                "inference_time_ms": tiempo_inferencia
            })
        }

    except Exception as e:
        publish_metric('TransaccionesFallidas', 1)
        error_msg = f"Error crítico procesando el evento S3. Detalle: {str(e)}"
        print(error_msg)
        raise e
