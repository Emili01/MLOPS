#!/usr/bin/env python3
"""
Pipeline MLOps Completo - Fase A
Bronze → Silver → Glue Catalog → Preparación para SageMaker
"""
import subprocess
import sys
from datetime import datetime

def run_step(description, command):
    print(f"\n{'='*60}")
    print(f" [{datetime.now().strftime('%H:%M:%S')}] {description}")
    print(f"{'='*60}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        print(f"❌ Error: {result.stderr}")
        sys.exit(1)
    print(f"✅ Completado")
    return True
run_step("Verificando conexión con LocalStack", "awslocal s3 ls")

# Pipeline principal
run_step("1/4 - Ingesta de datos (Bronze)", "python scripts/ingest/ingest_data.py")
run_step("2/4 - Transformación (Silver)", "python scripts/transform/transform_to_silver.py")
run_step("3/4 - Ejecutando Glue Crawler", 
         "awslocal glue start-crawler --name proyecto-ml-training-crawler && sleep 15")
run_step("4/4 - Verificando tablas en Glue Catalog", 
         "awslocal glue get-tables --database-name db_ml_analytics --query 'TableList[].Name'")

print("\n" + "="*60)
print("Pipeline Fase A completado exitosamente!")
print("="*60)
print("\nRecursos creados:")
print("  - S3://proyecto-ml-datalake/raw/    (Bronze)")
print("  - S3://proyecto-ml-datalake/silver/  (Silver)")
print("  - Glue Catalog: db_ml_analytics.raw  (Tabla catalogada)")
