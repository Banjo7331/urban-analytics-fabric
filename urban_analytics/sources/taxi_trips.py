from functools import reduce

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from urban_analytics.platform import Platform, Window
from urban_analytics.registry import Source, register

COLUMNS = {
    "VendorID": ("vendor_id", "int"),
    "tpep_pickup_datetime": ("pickup_at", "timestamp"),
    "tpep_dropoff_datetime": ("dropoff_at", "timestamp"),
    "passenger_count": ("passenger_count", "int"),
    "trip_distance": ("trip_distance_miles", "double"),
    "RatecodeID": ("rate_code_id", "int"),
    "store_and_fwd_flag": ("store_and_forward", "string"),
    "PULocationID": ("pickup_zone_id", "int"),
    "DOLocationID": ("dropoff_zone_id", "int"),
    "payment_type": ("payment_type", "int"),
    "fare_amount": ("fare_usd", "double"),
    "extra": ("extra_usd", "double"),
    "mta_tax": ("mta_tax_usd", "double"),
    "tip_amount": ("tip_usd", "double"),
    "tolls_amount": ("tolls_usd", "double"),
    "improvement_surcharge": ("improvement_surcharge_usd", "double"),
    "total_amount": ("total_usd", "double"),
    "congestion_surcharge": ("congestion_surcharge_usd", "double"),
    "Airport_fee": ("airport_fee_usd", "double"),
}

MAX_TRIP_MINUTES = 24 * 60
MAX_TRIP_MILES = 200
ZONE_RANGE = (1, 265)


def file_name(month: str) -> str:
    return f"yellow_tripdata_{month}.parquet"


def conform(df: DataFrame) -> DataFrame:
    present = {column.lower(): column for column in df.columns}
    selected = []
    for original, (target, kind) in COLUMNS.items():
        key = original.lower()
        value = F.col(present[key]) if key in present else F.lit(None)
        selected.append(value.cast(kind).alias(target))
    return df.select(selected)


def read_bronze(spark: SparkSession, platform: Platform) -> DataFrame:
    root = platform.bronze.files("taxi", "yellow")
    monthly = [
        conform(spark.read.parquet(f"{root}/{file_name(month)}")).withColumn("source_file", F.lit(file_name(month)))
        for month in platform.window.months()
    ]
    return reduce(DataFrame.unionByName, monthly)


def reject_reason(window: Window):
    return (
        F.when(F.col("pickup_at").isNull() | F.col("dropoff_at").isNull(), "missing_timestamp")
        .when(F.col("dropoff_at") <= F.col("pickup_at"), "non_positive_duration")
        .when(F.col("trip_minutes") > MAX_TRIP_MINUTES, "duration_over_24h")
        .when(~F.col("pickup_date").between(F.lit(window.start), F.lit(window.end)), "outside_window")
        .when(F.col("trip_distance_miles") < 0, "negative_distance")
        .when(F.col("trip_distance_miles") > MAX_TRIP_MILES, "distance_over_limit")
        .when(F.col("fare_usd") < 0, "negative_fare")
        .when(F.col("total_usd") < 0, "negative_total")
        .when(~F.col("pickup_zone_id").between(*ZONE_RANGE), "unknown_pickup_zone")
        .when(~F.col("dropoff_zone_id").between(*ZONE_RANGE), "unknown_dropoff_zone")
    )


def to_silver(df: DataFrame, platform: Platform) -> DataFrame:
    trip_columns = [column for column in df.columns if column != "source_file"]
    deduplicated = df.dropDuplicates(trip_columns)
    enriched = deduplicated.withColumns(
        {
            "pickup_date": F.to_date("pickup_at"),
            "pickup_hour": F.hour("pickup_at"),
            "pickup_month": F.date_format("pickup_at", "yyyy-MM"),
            "trip_minutes": (F.unix_timestamp("dropoff_at") - F.unix_timestamp("pickup_at")) / 60.0,
        }
    )
    return enriched.withColumn("reject_reason", reject_reason(platform.window))


register(Source("taxi_trips", read_bronze, to_silver, partition_by=("pickup_month",)))
