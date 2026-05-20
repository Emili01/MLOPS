import subprocess, sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "xgboost==1.7.6", "--quiet"])

import os
import json
import boto3
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.metrics import roc_auc_score, average_precision_score

class SiameseDataset(Dataset):
    def __init__(self, data_tensor, labels_tensor):
        self.data, self.labels = data_tensor, labels_tensor
    def __len__(self): return len(self.labels)
    def __getitem__(self, index):
        img1, label1 = self.data[index], self.labels[index]
        idx = np.random.choice(torch.where(self.labels == label1)[0].numpy()) if np.random.rand() > 0.5 else np.random.choice(torch.where(self.labels != label1)[0].numpy())
        target = torch.tensor(1.0 if label1 == self.labels[idx] else 0.0, dtype=torch.float32)
        return img1, self.data[idx], target

class DeepSiameseNetwork(nn.Module):
    def __init__(self, input_dim):
        super(DeepSiameseNetwork, self).__init__()
        self.fc = nn.Sequential(
            nn.Linear(input_dim, 64), nn.BatchNorm1d(64), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(64, 32), nn.BatchNorm1d(32), nn.ReLU(), nn.Linear(32, 16)
        )
    def forward(self, x1, x2): return self.fc(x1), self.fc(x2)

class ContrastiveLoss(nn.Module):
    def __init__(self, margin=2.5):
        super(ContrastiveLoss, self).__init__()
        self.margin = margin
    def forward(self, out1, out2, label):
        dist = F.pairwise_distance(out1, out2, keepdim=True)
        return torch.mean((label) * torch.pow(dist, 2) + (1 - label) * torch.pow(torch.clamp(self.margin - dist, min=0.0), 2))

def inject_features_for_training(df, model, ref_fraud):
    X_tensor = torch.FloatTensor(df.drop('Class', axis=1).values)
    with torch.no_grad():
        latents = model.fc(X_tensor)
        distances = F.pairwise_distance(latents, ref_fraud.unsqueeze(0).expand(X_tensor.size(0), -1)).numpy()
    df_aug = df.copy()
    for i in range(latents.shape[1]): df_aug[f'Latent_{i}'] = latents[:, i].numpy()
    df_aug['Siamese_Distance'] = distances
    return df_aug

if __name__ == '__main__':
    print("--- INICIANDO PIPELINE DE ENTRENAMIENTO AWS SAGEMAKER REAL ---")
    train_dir = os.environ.get('SM_CHANNEL_TRAIN', '/opt/ml/input/data/train')
    model_dir = os.environ.get('SM_MODEL_DIR', '/opt/ml/model')
    region    = os.environ.get('AWS_REGION', 'us-east-1')

    print(f"Leyendo datos desde: {train_dir}")
    df_raw = pd.read_parquet(train_dir)

    cols_to_drop = ['processed_at', 'source', 'version', 'Time', 'Amount']
    df_clean = df_raw.drop(columns=[col for col in cols_to_drop if col in df_raw.columns]).fillna(0)
    for col in df_clean.columns:
        df_clean[col] = pd.to_numeric(df_clean[col])

    input_dimension = df_clean.shape[1] - 1
    total_samples   = len(df_clean)
    fraud_samples   = int(df_clean['Class'].sum())
    normal_samples  = total_samples - fraud_samples

    print(f"Dimensiones: {input_dimension} features | Total: {total_samples} | Fraudes: {fraud_samples} | Normales: {normal_samples}")

    frauds      = df_clean[df_clean['Class'] == 1]
    normals     = df_clean[df_clean['Class'] == 0].sample(n=len(frauds) * 2, random_state=42)
    balanced_df = pd.concat([frauds, normals]).sample(frac=1).reset_index(drop=True)

    X = torch.FloatTensor(balanced_df.drop('Class', axis=1).values)
    y = torch.FloatTensor(balanced_df['Class'].values)

    print("Entrenando Red Siamesa...")
    model_siam = DeepSiameseNetwork(input_dimension)
    optimizer  = torch.optim.AdamW(model_siam.parameters(), lr=0.002)
    criterion  = ContrastiveLoss(margin=2.5)

    epoch_losses = []
    for epoch in range(30):
        model_siam.train()
        batch_losses = []
        for img1, img2, target in DataLoader(SiameseDataset(X, y), batch_size=128, shuffle=True):
            optimizer.zero_grad()
            out1, out2 = model_siam(img1, img2)
            loss = criterion(out1, out2, target.unsqueeze(1))
            loss.backward()
            optimizer.step()
            batch_losses.append(loss.item())
        epoch_loss = float(np.mean(batch_losses))
        epoch_losses.append(epoch_loss)
        if (epoch + 1) % 10 == 0:
            print(f"Epoch {epoch+1}/30 — Loss: {epoch_loss:.4f}")

    model_siam.eval()
    ref_fraud = torch.mean(model_siam.fc(torch.FloatTensor(frauds.drop('Class', axis=1).values)), dim=0)

    print("Inyectando latentes y entrenando XGBoost...")
    train_augmented = inject_features_for_training(df_clean, model_siam, ref_fraud)
    xgb_params = {
        'objective':        'binary:logistic',
        'eval_metric':      'aucpr',
        'tree_method':      'hist',
        'scale_pos_weight': 150,
        'max_depth':        6,
        'learning_rate':    0.05
    }
    dtrain    = xgb.DMatrix(train_augmented.drop('Class', axis=1), label=train_augmented['Class'])
    model_xgb = xgb.train(xgb_params, dtrain, num_boost_round=250)

    preds      = model_xgb.predict(dtrain)
    auc_roc    = float(roc_auc_score(train_augmented['Class'], preds))
    auc_pr     = float(average_precision_score(train_augmented['Class'], preds))
    final_loss = float(epoch_losses[-1])

    print(f"AUC-ROC:  {auc_roc:.4f}")
    print(f"AUC-PR:   {auc_pr:.4f}")
    print(f"Loss final siamesa: {final_loss:.4f}")

    try:
        cw = boto3.client('cloudwatch', region_name=region)
        cw.put_metric_data(
            Namespace='MLOps/FraudDetection',
            MetricData=[
                {'MetricName': 'TrainingAUC_ROC',  'Value': auc_roc,               'Unit': 'None'},
                {'MetricName': 'TrainingAUC_PR',   'Value': auc_pr,                'Unit': 'None'},
                {'MetricName': 'SiameseFinalLoss', 'Value': final_loss,            'Unit': 'None'},
                {'MetricName': 'TotalSamples',     'Value': float(total_samples),  'Unit': 'Count'},
                {'MetricName': 'FraudSamples',     'Value': float(fraud_samples),  'Unit': 'Count'},
                {'MetricName': 'NormalSamples',    'Value': float(normal_samples), 'Unit': 'Count'},
                {'MetricName': 'InputFeatures',    'Value': float(input_dimension),'Unit': 'Count'},
            ]
        )
        print("Metricas publicadas a CloudWatch correctamente.")
    except Exception as e:
        print(f"WARN: No se pudieron publicar metricas a CloudWatch: {e}")

    print("Guardando modelos...")
    torch.save(model_siam.state_dict(), os.path.join(model_dir, 'siamese.pth'))
    # CRITICO: guardar como .bin para que TorchServe no detecte dos archivos .pt/.pth
    torch.save(ref_fraud,               os.path.join(model_dir, 'reference.bin'))
    model_xgb.save_model(               os.path.join(model_dir, 'xgboost.json'))

    with open(os.path.join(model_dir, 'config.json'), 'w') as f:
        json.dump({
            'input_dim': input_dimension,
            'threshold': 0.90,
            'auc_roc':   auc_roc,
            'auc_pr':    auc_pr,
        }, f)

    print("--- ENTRENAMIENTO FINALIZADO CON EXITO ---")