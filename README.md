# Arquitectura MLOps para Detección de Fraudes

Este repositorio contiene el pipeline automatizado para el procesamiento de datos, entrenamiento de un modelo híbrido (Red Siamesa + XGBoost) y despliegue de un endpoint de inferencia para la detección de fraudes financieros utilizando infraestructura nativa de AWS.

## 🛠️ Tecnologías Utilizadas

| Categoría | Tecnología |
|---|---|
| Infraestructura como Código | Terraform |
| Procesamiento de Datos | AWS Glue (PySpark) |
| Orquestación | AWS Step Functions |
| Machine Learning | Amazon SageMaker (PyTorch + XGBoost) |
| Almacenamiento | Amazon S3 |
| Cómputo Serverless | AWS Lambda |
| Mensajería | Amazon SNS / SQS |
| Observabilidad | Amazon CloudWatch |

---

## 📐 Arquitectura del Pipeline

```
S3 Raw
  └─► Glue Job (PySpark)
        └─► S3 Silver (Parquet)
              └─► SageMaker Training (Red Siamesa + XGBoost)
                    └─► Lambda Repackage (inyecta inference.py en model.tar.gz)
                          └─► SageMaker Endpoint (InService)
                                └─► Lambda Trigger ──► SNS Notification
```

El pipeline está orquestado por **AWS Step Functions** y se dispara manualmente después del despliegue inicial de infraestructura.

---

## 📁 Estructura del Proyecto

```
MLOPS/
├── datasets/
│   └── creditcard.csv              # Dataset de entrenamiento (Credit Card Fraud)
├── scripts/
│   ├── glue/
│   │   └── transform_job.py        # Job PySpark: limpieza y feature engineering
│   ├── lambda/
│   │   ├── handler.py              # Lambda de inferencia (S3 trigger → SageMaker → SNS)
│   │   ├── train_trigger.py        # Lambda auxiliar de entrenamiento
│   │   └── repackage_model.py      # Lambda que empaqueta inference.py en model.tar.gz
│   ├── sagemaker/
│   │   ├── train_hybrid.py         # Script de entrenamiento (Red Siamesa + XGBoost)
│   │   ├── inference.py            # Script de inferencia para el endpoint
│   │   └── requirements.txt        # Dependencias del contenedor de entrenamiento
│   └── step_functions/
│       └── workflow.json           # Definición de la máquina de estados
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── s3.tf
│   ├── iam.tf
│   ├── glue.tf
│   ├── lambda.tf
│   ├── sagemaker.tf
│   ├── step_functions.tf
│   └── sqs_sns.tf
├── dummy_model.tar.gz              # Modelo dummy para arranque inicial del endpoint
├── prueba.py                       # Script de validación local del endpoint
└── README.md
```

---

## 📋 Prerrequisitos

Antes de comenzar, asegúrate de contar con las siguientes herramientas instaladas:

- Python 3.10 o superior
- Terraform >= 1.3
- AWS CLI configurado con permisos de administrador
- `pyarrow` instalado localmente para ejecutar `prueba.py`

```bash
pip install pyarrow boto3
```

---

## 🚀 Instrucciones de Despliegue

### 1. Autenticación en AWS

Configura tus credenciales de acceso para que la terminal pueda comunicarse con tu cuenta de AWS:

```bash
aws configure
```

Ingresa tu `Access Key ID`, `Secret Access Key`, región (`us-east-1`) y formato de salida (`json`).

---

### 2. Despliegue de Infraestructura con Terraform

Inicializa los proveedores y aprovisiona todos los recursos de la arquitectura. Terraform generará automáticamente los archivos `.zip` de las Lambdas — no es necesario empaquetar nada manualmente.

```bash
cd terraform
terraform init
terraform apply -auto-approve
cd ..
```

Recursos que se crearán:
- Buckets S3 (raw, silver, models, inference_input, scripts)
- Roles IAM para cada servicio
- Glue Crawler y Job
- Step Functions State Machine
- Lambda de inferencia y Lambda de reempaquetado
- SageMaker Model, Endpoint Config y Endpoint
- SNS Topic y SQS Dead Letter Queue
- CloudWatch Alarms

---

### 3. Carga del Dataset Crudo a S3

Sube el dataset de transacciones a la capa `raw` del Data Lake:

```bash
aws s3 cp datasets/creditcard.csv s3://proyecto-ml-datalake-lalo-ug-2026/raw/creditcard.csv
```

> **Nota:** Si modificas el nombre del bucket en `variables.tf`, actualiza esta ruta en consecuencia.

---

### 4. Disparo del Pipeline (Step Functions)

Ejecuta la máquina de estados. Este proceso corre secuencialmente:
1. **Glue Job** — limpieza, feature engineering y guardado en Parquet (S3 Silver)
2. **SageMaker Training** — entrena la Red Siamesa + XGBoost (~10 min)
3. **Lambda Repackage** — inyecta `inference.py` dentro del `model.tar.gz`
4. **SageMaker CreateModel + UpdateEndpoint** — actualiza el endpoint con el modelo real

```bash
aws stepfunctions start-execution \
  --state-machine-arn "arn:aws:states:us-east-1:<TU_ACCOUNT_ID>:stateMachine:proyecto-ml-pipeline" \
  --name "despliegue-$(date +%s)"
```

> Reemplaza `<TU_ACCOUNT_ID>` con tu ID de cuenta AWS (12 dígitos). Puedes obtenerlo con:
> ```bash
> aws sts get-caller-identity --query Account --output text
> ```

---

### 5. Monitoreo del Endpoint

El pipeline tarda aproximadamente **15-20 minutos** en completarse. Monitorea el estado del endpoint:

```bash
# Estado del pipeline
aws stepfunctions list-executions \
  --state-machine-arn "arn:aws:states:us-east-1:<TU_ACCOUNT_ID>:stateMachine:proyecto-ml-pipeline" \
  --max-results 1 \
  --query 'executions[0].{Status:status,Name:name}'

# Estado del endpoint
aws sagemaker describe-endpoint \
  --endpoint-name "proyecto-ml-endpoint" \
  --query 'EndpointStatus'
```

Espera hasta que el endpoint devuelva `"InService"`.

---

### 6. Validación del Endpoint

Con el endpoint activo, ejecuta el script de prueba. Este carga filas reales del parquet procesado y las envía al endpoint:

```bash
# Descargar muestra del parquet procesado (necesario la primera vez)
aws s3 cp s3://proyecto-ml-datalake-lalo-ug-2026/silver/$(aws s3 ls s3://proyecto-ml-datalake-lalo-ug-2026/silver/ | head -1 | awk '{print $4}') /tmp/sample.parquet

# Ejecutar prueba
python prueba.py
```

Salida esperada:
```
==============================================================
  #  Tipo                    Fraude      Prob
==============================================================
  1  fila_real_0           ✅ False    0.0123
  2  fila_real_1           ✅ False    0.0089
  3  fila_real_2           ✅ False    0.0201
  4  fila_real_3           ✅ False    0.0045
  5  fila_real_4           ✅ False    0.0312
==============================================================
```

---

### 7. Prueba del Flujo Completo Lambda → SNS

Para probar el trigger automático, sube un archivo JSON a `inference_input/`:

```bash
aws s3 cp /tmp/sample.parquet \
  s3://proyecto-ml-datalake-lalo-ug-2026/inference_input/test-$(date +%s).parquet
```

Esto dispara la Lambda de inferencia que consulta el endpoint y publica el resultado en SNS.

---

## 📊 Métricas de Entrenamiento (CloudWatch)

Las métricas se publican automáticamente bajo el namespace `MLOps/FraudDetection`:

```bash
aws cloudwatch get-metric-statistics \
  --namespace "MLOps/FraudDetection" \
  --metric-name "TrainingAUC_ROC" \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 3600 \
  --statistics Average
```

Métricas disponibles:
- `TrainingAUC_ROC` — AUC-ROC del modelo final
- `TrainingAUC_PR` — AUC Precision-Recall
- `SiameseFinalLoss` — Loss final de la red siamesa
- `TotalSamples` / `FraudSamples` / `NormalSamples` — distribución del dataset

---

## 🧹 Destruir la Infraestructura

Para eliminar todos los recursos y evitar costos:

```bash
cd terraform
terraform destroy -auto-approve
```

> **Importante:** El bucket S3 tiene `force_destroy = true`, por lo que se eliminará con todo su contenido.

---

## ⚠️ Notas Importantes

- El nombre del bucket `proyecto-ml-datalake-lalo-ug-2026` debe ser único globalmente. Si ya existe, cámbialo en `terraform/variables.tf`.
- El endpoint usa instancia `ml.m5.large` para garantizar suficiente memoria para PyTorch + XGBoost.
- El modelo dummy (`dummy_model.tar.gz`) es necesario para que el endpoint arranque antes de que el pipeline termine. No lo elimines del repositorio.
- El re-entrenamiento puede dispararse en cualquier momento volviendo a ejecutar el Step Functions (paso 4).
