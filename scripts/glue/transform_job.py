"""
Glue Job PySpark - Transformación Bronze → Silver
Dataset: Credit Card Fraud Detection
Compatible con Spark 3.5 + hadoop-aws 3.4.1
"""

import sys
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, when, lit, log1p, stddev, mean, 
    round as spark_round, sin, cos, sum as spark_sum
)
from datetime import datetime
import boto3
import os

os.environ['PYSPARK_PYTHON'] = '/home/emilio/miniconda3/envs/localstack-env/bin/python'
os.environ['PYSPARK_DRIVER_PYTHON'] = '/home/emilio/miniconda3/envs/localstack-env/bin/python'

S3_ENDPOINT = "http://localhost:4566"
BUCKET = "proyecto-ml-datalake"

def create_spark_session():
    spark = SparkSession.builder \
        .appName("CreditCard-Fraud-Bronze-to-Silver") \
        .config("spark.jars.packages", "org.apache.hadoop:hadoop-aws:3.4.1") \
        .config("spark.hadoop.fs.s3a.endpoint", S3_ENDPOINT) \
        .config("spark.hadoop.fs.s3a.access.key", "test") \
        .config("spark.hadoop.fs.s3a.secret.key", "test") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.connection.maximum", "100") \
        .config("spark.hadoop.fs.s3a.threads.max", "20") \
        .config("spark.driver.memory", "4g") \
        .config("spark.executor.memory", "4g") \
        .config("spark.hadoop.mapreduce.fileoutputcommitter.algorithm.version", "2") \
        .config("spark.sql.parquet.output.committer.class", "org.apache.parquet.hadoop.ParquetOutputCommitter") \
        .getOrCreate()
    return spark

def load_bronze_data(spark, file_key):
    s3_path = f"s3a://{BUCKET}/{file_key}"
    df = spark.read.csv(s3_path, header=True, inferSchema=True)
    print(f" Datos cargados: {df.count():,} filas, {len(df.columns)} columnas")
    return df

def validate_schema(df):
    expected_types = {
        'Time': 'double', 'Amount': 'double', 'Class': 'int',
        **{f'V{i}': 'double' for i in range(1, 29)}
    }
    for col_name, expected_type in expected_types.items():
        actual_type = df.schema[col_name].dataType.simpleString()
        if expected_type not in actual_type:
            print(f" {col_name}: esperado {expected_type}, actual {actual_type}")
    print("✅ Validación de schema completada")
    return True


def flag_outliers(df):
    from pyspark.sql.functions import expr
    
    columns_to_check = [c for c in df.columns if c not in ['Time', 'Class']]
    for col_name in columns_to_check:
        q1, q3 = df.approxQuantile(col_name, [0.25, 0.75], 0.01)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        df = df.withColumn(
            f"{col_name}_outlier",
            when((col(col_name) < lower) | (col(col_name) > upper), 1).otherwise(0)
        )
    
    outlier_cols = [f"{c}_outlier" for c in columns_to_check]
    sum_expr = " + ".join(outlier_cols)
    df = df.withColumn("is_outlier", when(expr(sum_expr) > 0, 1).otherwise(0))
    
    outlier_count = df.filter(col("is_outlier") == 1).count()
    print(f" Transacciones con outliers: {outlier_count:,} ({(outlier_count/df.count())*100:.2f}%)")
    return df



def transform_features(df):
    df = df.withColumn("hour_of_day", (col("Time") / 3600) % 24)
    df = df.withColumn("hour_sin", spark_round(sin(2 * 3.14159 * col("hour_of_day") / 24), 6))
    df = df.withColumn("hour_cos", spark_round(cos(2 * 3.14159 * col("hour_of_day") / 24), 6))
    df = df.withColumn("amount_log", spark_round(log1p(col("Amount")), 6))
    stats = df.select(mean("Amount"), stddev("Amount")).first()
    amount_mean, amount_std = stats[0], stats[1] if stats[1] > 0 else 1
    df = df.withColumn("amount_zscore", spark_round((col("Amount") - lit(amount_mean)) / lit(amount_std), 6))
    df = df.withColumn("high_amount", when(col("Amount") > 1000, 1).otherwise(0))
    print("✅ Features transformadas")
    return df

def add_metadata(df):
    df = df.withColumn("processed_at", lit(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    df = df.withColumn("source", lit("bronze_raw"))
    df = df.withColumn("version", lit("1.0"))
    return df

def save_to_silver(df, spark):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    silver_path = f"s3a://{BUCKET}/silver/creditcard_processed_{timestamp}"
    df.write.mode("overwrite").partitionBy("high_amount").parquet(silver_path)
    print(f" Datos guardados en Silver: {silver_path}")
    schema_df = spark.createDataFrame(
        [(col_name, str(dtype)) for col_name, dtype in df.dtypes],
        ["column_name", "data_type"]
    )
    schema_df.write.mode("overwrite").csv(f"s3a://{BUCKET}/silver/schema/")
    return silver_path

def run_pipeline(file_key=None):
    spark = create_spark_session()
    print("="*60)
    print(" INICIANDO GLUE JOB: BRONZE → SILVER")
    print("="*60)
    
    if not file_key:
        s3 = boto3.client('s3', endpoint_url=S3_ENDPOINT, aws_access_key_id='test', aws_secret_access_key='test')
        response = s3.list_objects_v2(Bucket=BUCKET, Prefix='raw/creditcard')
        files = [obj['Key'] for obj in response.get('Contents', []) if obj['Key'].endswith('.csv')]
        file_key = sorted(files)[-1] if files else None
    
    if not file_key:
        print("❌ No se encontraron archivos en raw/")
        spark.stop()
        return None
    
    print(f" Archivo fuente: {file_key}")
    df = load_bronze_data(spark, file_key)
    validate_schema(df)
    df = flag_outliers(df)
    df = transform_features(df)
    df = add_metadata(df)
    silver_path = save_to_silver(df, spark)
    
    print("\n" + "="*60)
    print("✅ GLUE JOB COMPLETADO EXITOSAMENTE")
    print(f"   Silver path: {silver_path}")
    print(f"   Columnas finales: {len(df.columns)}")
    print("="*60)
    
    spark.stop()
    return silver_path

if __name__ == "__main__":
    run_pipeline()
