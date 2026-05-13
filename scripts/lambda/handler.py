import os
import json
import boto3
import csv

# Inicialización de clientes fuera del handler para reutilizar conexiones (Mejor práctica en Lambda)
s3_client = boto3.client('s3')
sagemaker_client = boto3.client('sagemaker-runtime')
sns_client = boto3.client('sns')

# Variables de entorno inyectadas por Terraform
ENDPOINT_NAME = os.environ['SAGEMAKER_ENDPOINT']
SNS_TOPIC = os.environ['SNS_TOPIC_ARN']

def lambda_handler(event, context):
    try:
        # 1. Extraer el nombre del bucket y el archivo desde el evento de S3
        record = event['Records'][0]
        bucket_name = record['s3']['bucket']['name']
        file_key = record['s3']['object']['key']
        
        print(f"Procesando archivo: s3://{bucket_name}/{file_key}")

        # 2. Descargar el contenido del archivo desde S3 a la memoria de la Lambda
        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        file_content = response['Body'].read().decode('utf-8')

        # 3. Parsear los datos dinámicamente (Soporta JSON o CSV de 1 línea)
        transaction_data = {}
        
        if file_key.lower().endswith('.json'):
            transaction_data = json.loads(file_content)
        
        elif file_key.lower().endswith('.csv'):
            csv_reader = csv.DictReader(file_content.splitlines())
            transaction_data = next(csv_reader)
            
            # Convertir dinámicamente todo lo que sea numérico a float (para que SageMaker lo entienda)
            for key, value in transaction_data.items():
                try:
                    transaction_data[key] = float(value)
                except ValueError:
                    # Si no se puede convertir a float (ej. metadata como 'bronze_raw'), se deja como string
                    pass
        else:
            raise ValueError(f"Formato de archivo no soportado. Se esperaba .json o .csv, se recibió: {file_key}")

        # 4. Invocar al Endpoint de SageMaker
        print("Enviando payload a SageMaker...")
        sm_response = sagemaker_client.invoke_endpoint(
            EndpointName=ENDPOINT_NAME,
            ContentType='application/json',
            Body=json.dumps(transaction_data)
        )
        
        # 5. Procesar la respuesta del modelo híbrido
        result = json.loads(sm_response['Body'].read().decode('utf-8'))
        is_fraud = result.get('is_fraud', False)
        fraud_probability = result.get('fraud_probability', 0.0)
        
        print(f"Inferencia completada. ¿Es fraude?: {is_fraud} | Probabilidad: {fraud_probability}")

        # 6. Publicar alerta en SNS si se detecta fraude
        if is_fraud:
            mensaje_alerta = (
                f"🚨 ¡ALERTA CRÍTICA DE FRAUDE! 🚨\n\n"
                f"Se ha detectado una transacción anómala.\n"
                f"Archivo origen: s3://{bucket_name}/{file_key}\n"
                f"Probabilidad calculada por XGBoost: {fraud_probability:.4f}\n"
                f"Acción requerida: Revisión inmediata."
            )
            
            sns_client.publish(
                TopicArn=SNS_TOPIC,
                Message=mensaje_alerta,
                Subject="Alerta del Sistema de Prevención de Fraude"
            )
            print("Notificación de fraude enviada vía SNS.")

        return {
            "statusCode": 200, 
            "body": json.dumps({
                "message": "Transacción procesada correctamente",
                "file": file_key,
                "prediction": result
            })
        }
        
    except Exception as e:
        # En caso de cualquier fallo (lectura, parseo, timeout de SM), logueamos y lanzamos la excepción
        # Esto asegura que AWS envíe el evento a la DLQ de SQS automáticamente.
        error_msg = f"Error crítico procesando el evento S3. Detalle: {str(e)}"
        print(error_msg)
        raise e