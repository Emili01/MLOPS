# Proyecto MLOps - Credit Card Fraud Detection

## Requisitos
- Python 3.8+
- Java 8/11
- Docker + Docker Compose
- Cuenta LocalStack Pro (trial gratuito 45 días)

## Instalación rápida

```bash
# 1. Clonar repositorio
git clone <repo-url>
cd v1

# 2. Configurar entorno
chmod +x setup.sh
./setup.sh
source env/bin/activate

# 3. Configurar token LocalStack
cp .env.example .env
# Editar .env con tu token de https://app.localstack.cloud

# 4. Descargar dataset
python scripts/download_dataset.py

# 5. Iniciar infraestructura
docker-compose up -d
cd terraform
terraform init
terraform apply -auto-approve
cd ..

# 6. Ejecutar pipeline Fase A
python scripts/pipeline.py
