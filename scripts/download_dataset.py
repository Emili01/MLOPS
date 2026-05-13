#!/usr/bin/env python3
"""Descargar dataset Credit Card Fraud Detection"""
import os
import urllib.request

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_DIR = os.path.join(PROJECT_ROOT, 'datasets')
DATASET_PATH = os.path.join(DATASET_DIR, 'creditcard.csv')

os.makedirs(DATASET_DIR, exist_ok=True)

if os.path.exists(DATASET_PATH):
    print(f"✅ Dataset ya existe en {DATASET_PATH}")
else:
    print("Descargando Credit Card Fraud Detection dataset...")
    url = 'https://storage.googleapis.com/download.tensorflow.org/data/creditcard.csv'
    urllib.request.urlretrieve(url, DATASET_PATH)
  
    print(f"✅ Dataset descargado: {DATASET_PATH}")
