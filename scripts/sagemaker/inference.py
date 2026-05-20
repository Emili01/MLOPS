import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"

import sys
import subprocess

try:
    import xgboost as xgb
except ImportError:
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "xgboost==1.7.6"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    import xgboost as xgb

import json
import torch
import pandas as pd
import numpy as np
import torch.nn.functional as F

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
    siamese_path  = os.path.join(model_dir, 'siamese.pth')
    reference_path = os.path.join(model_dir, 'reference.bin')
    config_path   = os.path.join(model_dir, 'config.json')
    xgb_path      = os.path.join(model_dir, 'xgboost.json')

    # Si falta cualquier artefacto real, devolver dummy seguro
    for p in [siamese_path, reference_path, config_path, xgb_path]:
        if not os.path.exists(p) or os.path.getsize(p) < 10:
            print(f"Artefacto no encontrado o dummy: {p} — modo dummy activado.")
            return {'is_dummy': True, 'input_dim': 64}

    with open(config_path, 'r') as f:
        config = json.load(f)

    siam = DeepSiameseNetwork(config['input_dim'])
    siam.load_state_dict(torch.load(siamese_path, map_location='cpu'))
    siam.eval()

    # CRITICO: leer reference.bin (no reference.pt)
    ref = torch.load(reference_path, map_location='cpu')

    xgb_model = xgb.Booster()
    xgb_model.load_model(xgb_path)

    print(f"Modelo cargado correctamente. input_dim={config['input_dim']}, threshold={config['threshold']}")

    return {
        'siamese':   siam,
        'reference': ref,
        'xgboost':   xgb_model,
        'threshold': config['threshold'],
        'input_dim': config['input_dim'],
        'is_dummy':  False
    }

def input_fn(request_body, request_content_type):
    if request_content_type != 'application/json':
        raise ValueError(f"Content-type no soportado: {request_content_type}")
    data = json.loads(request_body)

    if isinstance(data, list):
        if len(data) > 0 and isinstance(data[0], list):
            return pd.DataFrame(data)
        return pd.DataFrame([data])
    if isinstance(data, dict):
        return pd.DataFrame([data])

    raise ValueError("Formato de entrada no reconocido.")

def predict_fn(input_data, models):
    if models.get('is_dummy'):
        return {
            'is_fraud':          False,
            'fraud_probability': 0.0,
            'threshold_used':    0.0,
            'msg':               'Modelo base activo. Ejecute Step Functions para entrenar.'
        }

    cols_to_drop = ['processed_at', 'source', 'version', 'Time', 'Amount', 'Class']
    df_clean = input_data.drop(columns=[c for c in cols_to_drop if c in input_data.columns])
    df_clean = df_clean.fillna(0)
    for col in df_clean.columns:
        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0)

    expected_dim = models['input_dim']
    actual_dim   = df_clean.shape[1]
    if actual_dim != expected_dim:
        raise ValueError(f"Dimension incorrecta: esperaba {expected_dim} features, recibio {actual_dim}.")

    X_tensor = torch.FloatTensor(df_clean.values)
    with torch.no_grad():
        latents = models['siamese'].fc(X_tensor)
        dist    = F.pairwise_distance(latents, models['reference'].unsqueeze(0)).numpy()

    for i in range(latents.shape[1]):
        df_clean[f'Latent_{i}'] = latents[:, i].numpy()
    df_clean['Siamese_Distance'] = dist

    dtest    = xgb.DMatrix(df_clean)
    prob     = float(models['xgboost'].predict(dtest)[0])
    is_fraud = prob > models['threshold']

    return {
        'is_fraud':          bool(is_fraud),
        'fraud_probability': round(prob, 6),
        'threshold_used':    models['threshold']
    }

def output_fn(prediction, accept):
    if accept in ('application/json', '*/*'):
        return json.dumps(prediction), 'application/json'
    raise ValueError(f"Accept no soportado: {accept}")