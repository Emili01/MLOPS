import os
import json
import torch
import pandas as pd
import numpy as np
import xgboost as xgb
import torch.nn.functional as F

# 1. Definición exacta de la arquitectura para poder cargar los pesos
class DeepSiameseNetwork(torch.nn.Module):
    def __init__(self, input_dim):
        super(DeepSiameseNetwork, self).__init__()
        self.fc = torch.nn.Sequential(
            torch.nn.Linear(input_dim, 64), torch.nn.BatchNorm1d(64), torch.nn.ReLU(), torch.nn.Dropout(0.3),
            torch.nn.Linear(64, 32), torch.nn.BatchNorm1d(32), torch.nn.ReLU(),
            torch.nn.Linear(32, 16)
        )
    def forward(self, x): 
        return self.fc(x)

def model_fn(model_dir):
    """Función de SageMaker: Carga los modelos en la memoria RAM del Endpoint al iniciar"""
    # Cargar configuración y metadatos guardados durante el entrenamiento
    with open(os.path.join(model_dir, 'config.json'), 'r') as f:
        config = json.load(f)
        
    # Inicializar y cargar pesos de la Red Siamesa
    siam = DeepSiameseNetwork(config['input_dim'])
    siam.load_state_dict(torch.load(os.path.join(model_dir, 'siamese.pth')))
    siam.eval() # Modo evaluación estricto
    
    # Cargar vector de referencia de fraude
    ref = torch.load(os.path.join(model_dir, 'reference.pt'))
    
    # Cargar el Booster final de XGBoost
    xgb_model = xgb.Booster()
    xgb_model.load_model(os.path.join(model_dir, 'xgboost.json'))
    
    return {
        'siamese': siam, 
        'reference': ref, 
        'xgboost': xgb_model, 
        'threshold': config['threshold']
    }

def input_fn(request_body, request_content_type):
    """Función de SageMaker: Convierte el JSON recibido de la Lambda a un DataFrame"""
    if request_content_type == 'application/json':
        data = json.loads(request_body)
        return pd.DataFrame([data])
    raise ValueError(f"Tipo de contenido no soportado: {request_content_type}")

def predict_fn(input_data, models):
    """Función de SageMaker: Ejecuta el pipeline Híbrido completo"""
    # 1. Filtro Quirúrgico de Metadata (Crucial para que no explote PyTorch)
    # Ignora cualquier columna de texto generada por la Fase A que no sea una feature numérica
    cols_to_drop = ['processed_at', 'source', 'version', 'Time', 'Amount']
    df_clean = input_data.drop(columns=[col for col in cols_to_drop if col in input_data.columns])
    
    # Rellenar posibles nulos y forzar valores numéricos
    df_clean = df_clean.fillna(0)
    for col in df_clean.columns: 
        df_clean[col] = pd.to_numeric(df_clean[col])

    # 2. Extracción de Características Siamesas (Mecanismo Híbrido)
    X_tensor = torch.FloatTensor(df_clean.values)
    with torch.no_grad():
        latents = models['siamese'].fc(X_tensor)
        dist = F.pairwise_distance(latents, models['reference'].unsqueeze(0)).numpy()
        
    # Engordar el DataFrame con las nuevas 17 columnas de conocimiento profundo
    for i in range(latents.shape[1]): 
        df_clean[f'Latent_{i}'] = latents[:, i].numpy()
    df_clean['Siamese_Distance'] = dist

    # 3. Predicción con XGBoost
    dtest = xgb.DMatrix(df_clean)
    prob = models['xgboost'].predict(dtest)[0] # Obtiene la probabilidad (0.0 a 1.0)
    
    # Evaluación contra el umbral óptimo (ej. 0.93)
    is_fraud = bool(prob > models['threshold'])
    
    return {
        'is_fraud': is_fraud, 
        'fraud_probability': float(prob)
    }

def output_fn(prediction, accept):
    """Función de SageMaker: Retorna la predicción a la Lambda"""
    if accept == 'application/json':
        return json.dumps(prediction), accept
    raise ValueError(f"Tipo de respuesta no soportado: {accept}")