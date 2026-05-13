import os
import json
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split

# --- 1. ARQUITECTURA DE LA RED ---
class SiameseDataset(Dataset):
    def __init__(self, data_tensor, labels_tensor):
        self.data = data_tensor
        self.labels = labels_tensor
        
    def __len__(self): 
        return len(self.labels)
        
    def __getitem__(self, index):
        img1 = self.data[index]
        label1 = self.labels[index]
        
        if np.random.rand() > 0.5:
            idx = np.random.choice(torch.where(self.labels == label1)[0].numpy())
        else:
            idx = np.random.choice(torch.where(self.labels != label1)[0].numpy())
            
        target = torch.tensor(1.0 if label1 == self.labels[idx] else 0.0, dtype=torch.float32)
        return img1, self.data[idx], target

class DeepSiameseNetwork(nn.Module):
    def __init__(self, input_dim):
        super(DeepSiameseNetwork, self).__init__()
        self.fc = nn.Sequential(
            nn.Linear(input_dim, 64), nn.BatchNorm1d(64), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(64, 32), nn.BatchNorm1d(32), nn.ReLU(),
            nn.Linear(32, 16)
        )
    def forward(self, x1, x2): 
        return self.fc(x1), self.fc(x2)

class ContrastiveLoss(nn.Module):
    def __init__(self, margin=2.5):
        super(ContrastiveLoss, self).__init__()
        self.margin = margin
    def forward(self, out1, out2, label):
        dist = F.pairwise_distance(out1, out2, keepdim=True)
        return torch.mean((label) * torch.pow(dist, 2) + (1 - label) * torch.pow(torch.clamp(self.margin - dist, min=0.0), 2))

def inject_features_for_training(df, model, ref_fraud):
    """Función utilitaria para engordar el dataset de entrenamiento antes de dárselo a XGBoost"""
    X_tensor = torch.FloatTensor(df.drop('Class', axis=1).values)
    with torch.no_grad():
        latents = model.fc(X_tensor)
        distances = F.pairwise_distance(latents, ref_fraud.unsqueeze(0).expand(X_tensor.size(0), -1)).numpy()
        
    df_aug = df.copy()
    for i in range(latents.shape[1]): 
        df_aug[f'Latent_{i}'] = latents[:, i].numpy()
    df_aug['Siamese_Distance'] = distances
    return df_aug

# --- 2. PIPELINE DE ENTRENAMIENTO (SAGEMAKER ENTRYPOINT) ---
if __name__ == '__main__':
    # Directorios estándar de AWS SageMaker
    train_dir = os.environ.get('SM_CHANNEL_TRAIN', '/opt/ml/input/data/train')
    model_dir = os.environ.get('SM_MODEL_DIR', '/opt/ml/model')

    print("--- INICIANDO PIPELINE DE ENTRENAMIENTO HÍBRIDO ---")
    
    # 1. Cargar el Parquet generado por la Fase A
    data_path = os.path.join(train_dir, 'fase_a_output.parquet')
    print(f"Cargando datos desde: {data_path}")
    df_raw = pd.read_parquet(data_path)
    
    # Limpieza de metadata para IA
    cols_to_drop = ['processed_at', 'source', 'version', 'Time', 'Amount']
    df_clean = df_raw.drop(columns=[col for col in cols_to_drop if col in df_raw.columns]).fillna(0)
    for col in df_clean.columns: 
        df_clean[col] = pd.to_numeric(df_clean[col])

    input_dimension = df_clean.shape[1] - 1 # Restamos la columna 'Class'
    print(f"Dimensiones limpias para la Red: {input_dimension} features.")

    # 2. Entrenar el Extractor de Características (PyTorch)
    print("Iniciando entrenamiento de la Red Siamesa...")
    frauds = df_clean[df_clean['Class'] == 1]
    normals = df_clean[df_clean['Class'] == 0].sample(n=len(frauds)*2, random_state=42)
    balanced_df = pd.concat([frauds, normals]).sample(frac=1).reset_index(drop=True)
    
    X = torch.FloatTensor(balanced_df.drop('Class', axis=1).values)
    y = torch.FloatTensor(balanced_df['Class'].values)
    
    model_siam = DeepSiameseNetwork(input_dimension)
    optimizer = torch.optim.AdamW(model_siam.parameters(), lr=0.002)
    criterion = ContrastiveLoss(margin=2.5)
    
    epochs = 30
    for epoch in range(epochs):
        model_siam.train()
        for img1, img2, target in DataLoader(SiameseDataset(X, y), batch_size=128, shuffle=True):
            optimizer.zero_grad()
            out1, out2 = model_siam(img1, img2)
            loss = criterion(out1, out2, target.unsqueeze(1))
            loss.backward()
            optimizer.step()
    
    model_siam.eval()
    ref_fraud = torch.mean(model_siam.fc(torch.FloatTensor(frauds.drop('Class', axis=1).values)), dim=0)
    print("Red Siamesa entrenada exitosamente.")

    # 3. Entrenar XGBoost con todo el Dataset
    print("Inyectando características latentes y entrenando XGBoost...")
    train_augmented = inject_features_for_training(df_clean, model_siam, ref_fraud)
    
    # Hiperparámetros fijados y validados de nuestra prueba Cross-Validation anidada
    xgb_params = {
        'objective': 'binary:logistic', 
        'eval_metric': 'aucpr', 
        'tree_method': 'hist', 
        'scale_pos_weight': 150, # Alta penalización por falsos negativos
        'max_depth': 6, 
        'learning_rate': 0.05
    }
    
    dtrain = xgb.DMatrix(train_augmented.drop('Class', axis=1), label=train_augmented['Class'])
    model_xgb = xgb.train(xgb_params, dtrain, num_boost_round=250)
    print("XGBoost entrenado exitosamente.")

    # 4. Guardar todos los artefactos
    print("Guardando modelos empaquetados en SM_MODEL_DIR...")
    torch.save(model_siam.state_dict(), os.path.join(model_dir, 'siamese.pth'))
    torch.save(ref_fraud, os.path.join(model_dir, 'reference.pt'))
    model_xgb.save_model(os.path.join(model_dir, 'xgboost.json'))
    
    # Guardar configuración para el endpoint de inferencia
    config = {
        'input_dim': input_dimension, 
        'threshold': 0.90 # Umbral de corte exigente para despliegue inicial
    }
    with open(os.path.join(model_dir, 'config.json'), 'w') as f:
        json.dump(config, f)
        
    print("--- ENTRENAMIENTO FINALIZADO. ARTEFACTOS LISTOS PARA EL ENDPOINT ---")