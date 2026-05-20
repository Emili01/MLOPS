import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql.functions import col, when, lit, log1p, stddev, mean, round as spark_round, sin, cos, expr
from datetime import datetime

# 1. Inicialización nativa de AWS Glue
args = getResolvedOptions(sys.argv, ['JOB_NAME'])
sc = SparkContext.getOrCreate()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

BUCKET = "proyecto-ml-datalake-lalo-ug-2026" # <--- Tu nuevo nombre único

print("="*60)
print(" INICIANDO GLUE JOB: BRONZE → SILVER")
print("="*60)

# 2. Leer de Bronze (Raw) - Usamos s3:// directo
raw_path = f"s3://{BUCKET}/raw/creditcard.csv"
print(f"-> Leyendo datos desde: {raw_path}")
df = spark.read.csv(raw_path, header=True, inferSchema=True)

# 3. Detectar Outliers
print("-> Calculando e identificando Outliers...")
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

# 4. Transformación de Features (Feature Engineering)
print("-> Transformando Features y normalizando variables...")
df = df.withColumn("hour_of_day", (col("Time") / 3600) % 24)
df = df.withColumn("hour_sin", spark_round(sin(2 * 3.14159 * col("hour_of_day") / 24), 6))
df = df.withColumn("hour_cos", spark_round(cos(2 * 3.14159 * col("hour_of_day") / 24), 6))
df = df.withColumn("amount_log", spark_round(log1p(col("Amount")), 6))

stats = df.select(mean("Amount"), stddev("Amount")).first()
amount_mean, amount_std = stats[0], stats[1] if stats[1] > 0 else 1
df = df.withColumn("amount_zscore", spark_round((col("Amount") - lit(amount_mean)) / lit(amount_std), 6))
df = df.withColumn("high_amount", when(col("Amount") > 1000, 1).otherwise(0))

# 5. Agregar Metadata
df = df.withColumn("processed_at", lit(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
df = df.withColumn("source", lit("bronze_raw"))

# 6. Guardar en Silver en formato PARQUET
silver_path = f"s3://{BUCKET}/silver/"
print(f"-> Guardando datos procesados en: {silver_path}")

df.write \
  .mode("overwrite") \
  .parquet(silver_path)

print("\n" + "="*60)
print("✅ GLUE JOB COMPLETADO EXITOSAMENTE")
print("="*60)

job.commit()