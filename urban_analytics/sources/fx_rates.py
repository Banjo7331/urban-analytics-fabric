from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from urban_analytics.checks import missing_number
from urban_analytics.platform import Platform
from urban_analytics.registry import Source, register
from urban_analytics.tables import load

BRONZE_TABLE = "ecb_fx_usd_eur"


def read_bronze(spark: SparkSession, platform: Platform) -> DataFrame:
    return load(spark, platform.bronze.table(BRONZE_TABLE))


def to_silver(df: DataFrame, platform: Platform) -> DataFrame:
    rates = df.select(
        F.col("rate_date").cast("date").alias("rate_date"),
        F.col("usd_per_eur").cast("double").alias("usd_per_eur"),
    )
    reason = (
        F.when(F.col("rate_date").isNull(), "missing_date")
        .when(missing_number("usd_per_eur"), "missing_value")
        .when(F.col("usd_per_eur") <= 0, "non_positive_rate")
    )
    return rates.dropDuplicates(["rate_date"]).withColumn("reject_reason", reason)


register(Source("fx_rates_daily", read_bronze, to_silver))
