#!/bin/bash
# ==========================================
# SETUP AUTOMATIZADO - MLOPS (FASE A + FASE B)
# ==========================================

echo "🚀 Configurando entorno MLOps local..."

# 1. Verificar dependencias base
python3 --version || { echo "❌ Error: Python 3 es requerido"; exit 1; }
java -version 2>&1 | head -1 || { echo "❌ Error: Java 8/11 es requerido (para PySpark en la Fase A)"; exit 1; }

# 2. Entorno Virtual
echo "📦 Creando entorno virtual..."
python3 -m venv env
source env/bin/activate

# 3. Instalación de librerías
echo "📥 Instalando dependencias de requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. Empaquetado de la IA para AWS SageMaker (Fase B)
echo "🗜️ Empaquetando scripts híbridos de SageMaker..."
cd scripts/sagemaker
rm -f sourcedir.tar.gz 
tar -czvf sourcedir.tar.gz train_hybrid.py inference.py requirements.txt
cd ../../

# 5. Crear modelo temporal (Dummy) para engañar a Terraform
echo "🎩 Creando modelo dummy temporal para Terraform..."
echo "dummy" > dummy.txt
tar -czvf dummy_model.tar.gz dummy.txt
rm dummy.txt

echo "=========================================="
echo "✅ Entorno local configurado y scripts empaquetados exitosamente."
echo "✅ Siguiente paso: Ejecutar 'source env/bin/activate' en tu terminal."
echo "=========================================="