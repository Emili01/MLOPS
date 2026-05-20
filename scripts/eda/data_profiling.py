import pandas as pd
import numpy as np
from datetime import datetime
import json
import os
import boto3

BUCKET = os.getenv('S3_BUCKET', 'proyecto-ml-datalake-lalo-ug-2026') # <--- Tu nuevo nombre único

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DATASET_PATH = os.path.join(PROJECT_ROOT, 'datasets', 'creditcard.csv')

# Cliente limpio para la nube real
s3 = boto3.client('s3')

def load_data():
    """Cargar dataset desde datasets/"""
    df = pd.read_csv(DATASET_PATH)
    print(f" Dataset cargado: {df.shape[0]:,} filas, {df.shape[1]} columnas")
    return df

def analyze_nulls(df):
    """Identificar valores nulos"""
    nulls = df.isnull().sum()
    nulls_pct = (nulls / len(df)) * 100
    null_report = pd.DataFrame({
        'column': nulls.index,
        'null_count': nulls.values,
        'null_percentage': nulls_pct.values
    })
    null_report = null_report[null_report['null_count'] > 0].sort_values('null_percentage', ascending=False)
    return null_report

def detect_outliers(df, method='iqr'):
    """Detectar outliers usando IQR"""
    outliers_report = {}
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    
    for col in numeric_cols:
        if col != 'Class':  # No analizar la variable target
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            
            outliers = df[(df[col] < lower_bound) | (df[col] > upper_bound)]
            if len(outliers) > 0:
                outliers_report[col] = {
                    'count': len(outliers),
                    'percentage': (len(outliers) / len(df)) * 100,
                    'lower_bound': lower_bound,
                    'upper_bound': upper_bound,
                    'Q1': Q1,
                    'Q3': Q3,
                    'IQR': IQR
                }
    return outliers_report

def analyze_class_distribution(df):
    """Analizar distribución de clases (desbalance)"""
    class_dist = df['Class'].value_counts()
    return {
        'genuine': int(class_dist[0]),
        'fraud': int(class_dist[1]),
        'fraud_percentage': float((class_dist[1] / len(df)) * 100),
        'ratio': float(class_dist[0] / class_dist[1])
    }

def basic_statistics(df):
    """Estadísticas básicas"""
    stats = {}
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    
    for col in numeric_cols:
        if col != 'Time':  
            stats[col] = {
                'mean': float(df[col].mean()),
                'std': float(df[col].std()),
                'min': float(df[col].min()),
                'max': float(df[col].max()),
                'skewness': float(df[col].skew())
            }
    return stats

def generate_report(df):
    """Generar reporte completo"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    report = {
        'timestamp': timestamp,
        'dataset_shape': {'rows': len(df), 'columns': len(df.columns)},
        'columns': list(df.columns),
        'dtypes': df.dtypes.astype(str).to_dict(),
        'null_analysis': analyze_nulls(df).to_dict('records') if len(analyze_nulls(df)) > 0 else 'No nulls found ✅',
        'outliers': detect_outliers(df),
        'class_distribution': analyze_class_distribution(df),
        'basic_statistics': basic_statistics(df)
    }
    
    return report, timestamp

def save_report(report, timestamp):
    """Guardar reporte en S3 (capa reports/)"""
    report_json = json.dumps(report, indent=2)
    s3.put_object(
        Bucket=BUCKET,
        Key=f'reports/data_profile_{timestamp}.json',
        Body=report_json
    )
    print(f" Reporte guardado en: s3://{BUCKET}/reports/data_profile_{timestamp}.json")
    
    os.makedirs('../../datasets/reports', exist_ok=True)
    with open(f'../../datasets/reports/data_profile_{timestamp}.json', 'w') as f:
        f.write(report_json)

def print_summary(report):
    """Imprimir resumen en consola"""
    print("\n" + "="*60)
    print(" RESUMEN DE DATA PROFILING")
    print("="*60)
    
    print(f"\n Dimensiones: {report['dataset_shape']['rows']:,} filas × {report['dataset_shape']['columns']} columnas")
    
    print("\n Valores Nulos:")
    if isinstance(report['null_analysis'], str):
        print(f"  {report['null_analysis']}")
    else:
        for item in report['null_analysis']:
            print(f"  {item['column']}: {item['null_count']:,} ({item['null_percentage']:.2f}%)")
    
    print(f"\n  Distribución de Clases:")
    print(f"  Genuinas: {report['class_distribution']['genuine']:,}")
    print(f"  Fraudes:  {report['class_distribution']['fraud']:,}")
    print(f"  % Fraude: {report['class_distribution']['fraud_percentage']:.4f}%")
    print(f"  Ratio:    1:{report['class_distribution']['ratio']:.0f}")
    
    print(f"\n Outliers Detectados:")
    total_outliers = 0
    for col, info in report['outliers'].items():
        if info['percentage'] > 0.1:  
            print(f"  {col}: {info['count']:,} ({info['percentage']:.2f}%)")
            total_outliers += info['count']
    print(f"  Total columnas con outliers: {len(report['outliers'])}")
    
    print("="*60)

def main():
    print(" Iniciando Data Profiling...")

    df = load_data()    
    report, timestamp = generate_report(df)
    print_summary(report)
    save_report(report, timestamp)
    
    print(f"\n✅ Data Profiling completado")

if __name__ == "__main__":
    main()
