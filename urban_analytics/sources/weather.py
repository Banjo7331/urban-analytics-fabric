from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from urban_analytics.checks import missing_number
from urban_analytics.platform import Platform
from urban_analytics.registry import Source, register
from urban_analytics.tables import load

BRONZE_TABLE = "openmeteo_daily"
MEASURES = {
    "temperature_max_c": "double",
    "temperature_min_c": "double",
    "temperature_mean_c": "double",
    "precipitation_mm": "double",
    "rain_mm": "double",
    "snowfall_cm": "double",
    "wind_speed_max_kmh": "double",
}


def read_bronze(spark: SparkSession, platform: Platform) -> DataFrame:
    return load(spark, platform.bronze.table(BRONZE_TABLE))


def to_silver(df: DataFrame, platform: Platform) -> DataFrame:
    window = platform.window
    weather = df.select(
        F.col("weather_date").cast("date").alias("weather_date"),
        *[F.col(name).cast(kind).alias(name) for name, kind in MEASURES.items()],
    )
    reason = (
        F.when(F.col("weather_date").isNull(), "missing_date")
        .when(missing_number("temperature_mean_c"), "missing_temperature")
        .when(F.col("temperature_max_c") < F.col("temperature_min_c"), "inverted_temperature_range")
        .when(F.col("precipitation_mm") < 0, "negative_precipitation")
        .when(~F.col("weather_date").between(F.lit(window.start), F.lit(window.end)), "outside_window")
    )
    return weather.dropDuplicates(["weather_date"]).withColumn("reject_reason", reason)


register(Source("weather_daily", read_bronze, to_silver))
