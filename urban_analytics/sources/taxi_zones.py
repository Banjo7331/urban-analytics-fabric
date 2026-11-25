from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from urban_analytics.platform import Platform
from urban_analytics.registry import Source, register

FILE = "taxi_zone_lookup.csv"


def read_bronze(spark: SparkSession, platform: Platform) -> DataFrame:
    return spark.read.option("header", True).csv(platform.bronze.files("taxi", "zones", FILE))


def to_silver(df: DataFrame, platform: Platform) -> DataFrame:
    zones = df.select(
        F.col("LocationID").cast("int").alias("zone_id"),
        F.trim("Borough").alias("borough"),
        F.trim("Zone").alias("zone_name"),
        F.trim("service_zone").alias("service_zone"),
    )
    return zones.dropDuplicates(["zone_id"]).withColumn(
        "reject_reason", F.when(F.col("zone_id").isNull(), "missing_zone_id")
    )


register(Source("taxi_zones", read_bronze, to_silver))
