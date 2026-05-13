#!/usr/bin/env python3
"""
Pipeline MLOps Completo - Fase A
Flujo: Ingesta → EDA → Glue Job → Crawler → Catálogo
"""
import subprocess
import sys
import os
from datetime import datetime

# IMPORTANTE: Usar el Python del entorno conda
PYTHON_ENV = "/home/emilio/miniconda3/envs/localstack-env/bin/python"
PROJECT_ROOT = "/home/emilio/Documentos/CN/practicaFinal/v1"

def run_step(description, command, sleep=0):
    print(f"\n{'='*60}")
    print(f" [{datetime.now().strftime('%H:%M:%S')}] {description}")
    print(f"{'='*60}")
    
    # Ejecutar con el Python del entorno correcto
    result = subprocess.run(command, shell=True, capture_output=True, 
                          text=True, cwd=PROJECT_ROOT)
    
    if result.stdout:
        # Filtrar warnings de Spark para mejor legibilidad
        stdout_lines = result.stdout.split('\n')
        for line in stdout_lines:
            if 'WARN' not in line and 'SLF4J' not in line:
                print(line)
    
    if result.returncode != 0:
        # Mostrar solo errores relevantes
        stderr_lines = result.stderr.split('\n')
        for line in stderr_lines:
            if 'Error' in line or 'Exception' in line or 'Traceback' in line:
                print(f"❌ {line}")
        sys.exit(1)
    
    if sleep:
        import time
        print(f" Esperando {sleep}s...")
        time.sleep(sleep)
    
    print(f"✅ Completado")
    return True

# Verificar que existe el entorno
if not os.path.exists(PYTHON_ENV):
    print(f"❌ No se encuentra Python en: {PYTHON_ENV}")
    sys.exit(1)

print(" Usando Python del entorno localstack-env")

# 1. Verificar conexión
run_step("Verificando conexión con LocalStack", "awslocal s3 ls")

# 2. Ingesta a Bronze
run_step("1/5 - Ingesta de datos (Bronze)", 
         f"{PYTHON_ENV} {PROJECT_ROOT}/scripts/ingest/ingest_data.py")

# 3. Data Profiling (EDA)
run_step("2/5 - Análisis exploratorio (EDA)", 
         f"{PYTHON_ENV} {PROJECT_ROOT}/scripts/eda/data_profiling.py")

# 4. Glue Job PySpark
run_step("3/5 - Glue Job PySpark (Bronze → Silver)", 
         f"{PYTHON_ENV} {PROJECT_ROOT}/scripts/glue/transform_job.py")

# 5. Glue Crawler
run_step("4/5 - Ejecutando Glue Crawler en Silver", 
         "awslocal glue start-crawler --name proyecto-ml-silver-crawler",
         sleep=25)

# 6. Verificar catálogo
run_step("5/5 - Verificando tablas en Glue Catalog", 
         "awslocal glue get-tables --database-name db_ml_analytics --query 'TableList[].Name'")

print("\n" + "="*60)
print(" FASE A COMPLETADA EXITOSAMENTE!")
print("="*60)
print("\n Recursos creados:")
print("  ✅ S3://proyecto-ml-datalake/raw/              (Bronze - CSV)")
print("  ✅ S3://proyecto-ml-datalake/reports/           (EDA)")
print("  ✅ S3://proyecto-ml-datalake/silver/            (Silver - Parquet)")
print("  ✅ Glue Catalog: db_ml_analytics                (3 tablas)")
print("\n Listo para Fase B: Entrenamiento con SageMaker")
