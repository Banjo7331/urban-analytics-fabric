from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window as SparkWindow

from urban_analytics.platform import Platform
from urban_analytics.tables import load


def date_key(column: str):
    return F.date_format(column, "yyyyMMdd").cast("int")


def calendar(spark: SparkSession, platform: Platform) -> DataFrame:
    window = platform.window
    return spark.sql(
        f"SELECT explode(sequence(DATE '{window.start}', DATE '{window.end}', INTERVAL 1 DAY)) AS full_date"
    )


def dim_date(spark: SparkSession, platform: Platform) -> DataFrame:
    days = calendar(spark, platform)
    weekday = F.dayofweek("full_date")
    return days.select(
        date_key("full_date").alias("date_key"),
        F.col("full_date"),
        F.year("full_date").alias("year"),
        F.quarter("full_date").alias("quarter"),
        F.month("full_date").alias("month"),
        F.date_format("full_date", "MMMM").alias("month_name"),
        F.dayofmonth("full_date").alias("day"),
        F.when(weekday == 1, 7).otherwise(weekday - 1).alias("day_of_week"),
        F.date_format("full_date", "EEEE").alias("day_name"),
        F.weekofyear("full_date").alias("week_of_year"),
        weekday.isin(1, 7).alias("is_weekend"),
    )


def dim_zone(spark: SparkSession, platform: Platform) -> DataFrame:
    zones = load(spark, platform.silver.table("taxi_zones"))
    return zones.select(
        F.col("zone_id").alias("zone_key"),
        "borough",
        "zone_name",
        "service_zone",
        F.col("service_zone").isin("Airports").alias("is_airport"),
    )


def dim_station(spark: SparkSession, platform: Platform) -> DataFrame:
    measurements = load(spark, platform.silver.table("air_quality_hourly"))
    latest = SparkWindow.partitionBy("station_id").orderBy(F.col("measured_at").desc())
    return (
        measurements.withColumn("rank", F.row_number().over(latest))
        .filter(F.col("rank") == 1)
        .select(
            F.col("station_id").alias("station_key"),
            "station_name",
            "latitude",
            "longitude",
        )
    )


def dim_fx(spark: SparkSession, platform: Platform) -> DataFrame:
    rates = load(spark, platform.silver.table("fx_rates_daily"))
    days = calendar(spark, platform)
    joined = days.join(rates, days.full_date == rates.rate_date, "left").select("full_date", "usd_per_eur")
    backward = SparkWindow.orderBy("full_date").rowsBetween(SparkWindow.unboundedPreceding, 0)
    forward = SparkWindow.orderBy("full_date").rowsBetween(0, SparkWindow.unboundedFollowing)
    filled = F.coalesce(
        F.last("usd_per_eur", ignorenulls=True).over(backward),
        F.first("usd_per_eur", ignorenulls=True).over(forward),
    )
    return joined.select(
        date_key("full_date").alias("date_key"),
        "full_date",
        filled.alias("usd_per_eur"),
        (F.lit(1.0) / filled).alias("eur_per_usd"),
        F.col("usd_per_eur").isNull().alias("is_carried_forward"),
    )


def dim_gdp(spark: SparkSession, platform: Platform) -> DataFrame:
    gdp = load(spark, platform.silver.table("gdp_annual"))
    return gdp.select("country_code", "country_name", "year", "gdp_usd")
