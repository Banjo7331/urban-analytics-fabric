from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from urban_analytics.gold.dimensions import date_key
from urban_analytics.platform import Platform
from urban_analytics.tables import load

PARAMETERS = ("pm25", "no2", "o3")
MIN_CORRELATION_DAYS = 20


def money(column):
    return F.round(column, 2)


def fact_taxi_daily(spark: SparkSession, platform: Platform, fx: DataFrame) -> DataFrame:
    trips = load(spark, platform.silver.table("taxi_trips"))
    daily = trips.groupBy("pickup_date", "pickup_zone_id").agg(
        F.count("*").alias("trips"),
        F.sum("passenger_count").alias("passengers"),
        F.round(F.sum("trip_distance_miles"), 2).alias("distance_miles"),
        money(F.sum("fare_usd")).alias("fare_usd"),
        money(F.sum("tip_usd")).alias("tip_usd"),
        money(F.sum("total_usd")).alias("revenue_usd"),
        F.round(F.avg("trip_minutes"), 2).alias("avg_trip_minutes"),
    )
    with_key = daily.withColumn("date_key", date_key("pickup_date"))
    return with_key.join(fx.select("date_key", "usd_per_eur"), "date_key", "left").select(
        "date_key",
        F.col("pickup_zone_id").alias("pickup_zone_key"),
        "trips",
        "passengers",
        "distance_miles",
        "fare_usd",
        "tip_usd",
        "revenue_usd",
        money(F.col("revenue_usd") / F.col("usd_per_eur")).alias("revenue_eur"),
        "avg_trip_minutes",
    )


def fact_taxi_hourly(spark: SparkSession, platform: Platform) -> DataFrame:
    trips = load(spark, platform.silver.table("taxi_trips"))
    hourly = trips.groupBy("pickup_date", "pickup_hour").agg(
        F.count("*").alias("trips"),
        money(F.sum("total_usd")).alias("revenue_usd"),
        F.round(F.avg("trip_minutes"), 2).alias("avg_trip_minutes"),
        F.round(F.avg("trip_distance_miles"), 2).alias("avg_distance_miles"),
    )
    return hourly.select(
        date_key("pickup_date").alias("date_key"),
        F.col("pickup_hour").alias("hour"),
        "trips",
        "revenue_usd",
        "avg_trip_minutes",
        "avg_distance_miles",
    )


def fact_air_quality_daily(spark: SparkSession, platform: Platform) -> DataFrame:
    measurements = load(spark, platform.silver.table("air_quality_hourly"))
    daily = measurements.groupBy("measured_date", "station_id", "parameter", "unit").agg(
        F.round(F.avg("value"), 3).alias("avg_value"),
        F.round(F.min("value"), 3).alias("min_value"),
        F.round(F.max("value"), 3).alias("max_value"),
        F.count("*").alias("samples"),
    )
    return daily.select(
        date_key("measured_date").alias("date_key"),
        F.col("station_id").alias("station_key"),
        "parameter",
        "unit",
        "avg_value",
        "min_value",
        "max_value",
        "samples",
    )


def fact_air_quality_hourly(spark: SparkSession, platform: Platform) -> DataFrame:
    measurements = load(spark, platform.silver.table("air_quality_hourly"))
    hourly = measurements.groupBy("measured_date", "measured_hour", "parameter").agg(
        F.round(F.avg("value"), 3).alias("avg_value"),
        F.count("*").alias("samples"),
    )
    return hourly.select(
        date_key("measured_date").alias("date_key"),
        F.col("measured_hour").alias("hour"),
        "parameter",
        "avg_value",
        "samples",
    )


def city_pollution_daily(air_quality_daily: DataFrame) -> DataFrame:
    city = air_quality_daily.groupBy("date_key", "parameter").agg(F.avg("avg_value").alias("city_value"))
    pivoted = city.groupBy("date_key").pivot("parameter", list(PARAMETERS)).agg(F.first("city_value"))
    return pivoted.select(
        "date_key",
        *[F.round(F.col(parameter), 3).alias(f"avg_{parameter}") for parameter in PARAMETERS],
    )


def fact_urban_daily(
    spark: SparkSession,
    platform: Platform,
    dates: DataFrame,
    taxi_daily: DataFrame,
    air_quality_daily: DataFrame,
    fx: DataFrame,
) -> DataFrame:
    weather = load(spark, platform.silver.table("weather_daily")).withColumn("date_key", date_key("weather_date"))
    city_taxi = taxi_daily.groupBy("date_key").agg(
        F.sum("trips").alias("trips"),
        money(F.sum("revenue_usd")).alias("revenue_usd"),
        money(F.sum("revenue_eur")).alias("revenue_eur"),
        F.round(F.sum("distance_miles") / F.sum("trips"), 2).alias("avg_distance_miles"),
    )
    pollution = city_pollution_daily(air_quality_daily)
    return (
        dates.select("date_key", "full_date", "is_weekend")
        .join(city_taxi, "date_key", "left")
        .join(pollution, "date_key", "left")
        .join(
            weather.select(
                "date_key", "temperature_mean_c", "temperature_max_c", "precipitation_mm", "snowfall_cm", "wind_speed_max_kmh"
            ),
            "date_key",
            "left",
        )
        .join(fx.select("date_key", "usd_per_eur"), "date_key", "left")
        .orderBy("date_key")
    )


def fact_zone_station_correlation(taxi_daily: DataFrame, air_quality_daily: DataFrame) -> DataFrame:
    zone_days = taxi_daily.select("date_key", "pickup_zone_key", "trips")
    station_days = air_quality_daily.select("date_key", "station_key", "parameter", "avg_value")
    paired = zone_days.join(station_days, "date_key")
    correlated = paired.groupBy("pickup_zone_key", "station_key", "parameter").agg(
        F.round(F.corr("trips", "avg_value"), 4).alias("pearson_r"),
        F.count("*").alias("days"),
        F.round(F.avg("trips"), 1).alias("avg_daily_trips"),
    )
    return correlated.filter(F.col("days") >= MIN_CORRELATION_DAYS).filter(F.col("pearson_r").isNotNull()).select(
        F.col("pickup_zone_key").alias("zone_key"), "station_key", "parameter", "pearson_r", "days", "avg_daily_trips"
    )
