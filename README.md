# Proyecto MLOps - Credit Card Fraud Detection

## Requisitos
- Python 3.8+
- iNTERNET ESTABLE
- TERRAFORM INSTALADO
- UNA CUENTA DE AWS CON CREDITOS OBVIAMENTE

## EJECUCION Y PRUEBA

Descargar dataset
python scripts/download_dataset.py

### 1. Autenticación en AWS
Configura tus credenciales de acceso locales para que la terminal pueda comunicarse de forma segura con tu infraestructura en la nube.
```bash
aws configure

### 2. Despĺiegues de infraestructura
cd terraform
terraform init
terraform apply -auto-approve
cd ..

### 3. Carga del dataset
aws s3 cp datasets/creditcard.csv s3://proyecto-ml-datalake-lalo-ug-2026/raw/

### 4. Ejecucion de la maquina de estado
aws stepfunctions start-execution \
  --state-machine-arn "arn:aws:states:us-east-1:<TU_ID_DE_CUENTA_AWS>:stateMachine:proyecto-ml-pipeline" \
  --name "despliegue-final-$(date +%s)"

### 4. Monitores
El pipeline creará o actualizará un Endpoint de SageMaker llamado proyecto-ml-endpoint. Ejecuta el siguiente comando para monitorear su estado hasta que cambie formalmente a "InService"}
aws sagemaker describe-endpoint \
  --endpoint-name "proyecto-ml-endpoint" \
  --query 'EndpointStatus'

### 5. Ejecucion de pruebas
python prueba.py

