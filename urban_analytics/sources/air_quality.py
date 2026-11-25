from pyspark.sql import Column, DataFrame, SparkSession
from pyspark.sql import functions as F

from urban_analytics.checks import missing_number
from urban_analytics.platform import Platform
from urban_analytics.registry import Source, register
from urban_analytics.tables import load

BRONZE_TABLE = "openaq_hourly"
PARAMETERS = ("pm25", "no2", "o3")
LOCAL_TIMEZONE = "America/New_York"
TARGET_UNIT = "µg/m³"
MOLAR_VOLUME_LITRES = 24.45
MOLAR_MASS = {"no2": 46.0055, "o3": 47.9982}
MIXING_RATIO_TO_PPB = {"ppm": 1000.0, "ppb": 1.0}
MASS_CONCENTRATION_UNITS = ("ug/m3",)


def read_bronze(spark: SparkSession, platform: Platform) -> DataFrame:
    return load(spark, platform.bronze.table(BRONZE_TABLE))


def normalized_unit(column: str) -> Column:
    lowered = F.lower(F.trim(column))
    return F.regexp_replace(F.regexp_replace(lowered, "[µμ]", "u"), "³", "3")


def to_mass_concentration(value: Column, parameter: Column, unit: Column) -> Column:
    converted = F.when(unit.isin(*MASS_CONCENTRATION_UNITS), value)
    for mixing_unit, to_ppb in MIXING_RATIO_TO_PPB.items():
        for gas, molar_mass in MOLAR_MASS.items():
            factor = to_ppb * molar_mass / MOLAR_VOLUME_LITRES
            converted = converted.when((unit == mixing_unit) & (parameter == gas), value * factor)
    return converted


def to_silver(df: DataFrame, platform: Platform) -> DataFrame:
    window = platform.window
    measurements = df.select(
        F.col("location_id").cast("int").alias("station_id"),
        F.trim("location_name").alias("station_name"),
        F.col("sensor_id").cast("int").alias("sensor_id"),
        F.lower(F.trim("parameter")).alias("parameter"),
        F.trim("unit").alias("source_unit"),
        F.col("latitude").cast("double").alias("latitude"),
        F.col("longitude").cast("double").alias("longitude"),
        F.col("value").cast("double").alias("source_value"),
        F.col("datetime_from_utc").cast("timestamp").alias("measured_at_utc"),
    )
    measured_at = F.from_utc_timestamp("measured_at_utc", LOCAL_TIMEZONE)
    value = to_mass_concentration(F.col("source_value"), F.col("parameter"), normalized_unit("source_unit"))
    enriched = measurements.withColumns(
        {
            "value": F.round(value, 3),
            "unit": F.lit(TARGET_UNIT),
            "measured_at": measured_at,
            "measured_date": F.to_date(measured_at),
            "measured_hour": F.hour(measured_at),
        }
    )
    deduplicated = enriched.dropDuplicates(["sensor_id", "measured_at_utc"])
    reason = (
        F.when(F.col("measured_at_utc").isNull(), "missing_timestamp")
        .when(missing_number("source_value"), "missing_value")
        .when(F.col("source_value") < 0, "negative_value")
        .when(~F.col("parameter").isin(*PARAMETERS), "unsupported_parameter")
        .when(F.col("value").isNull(), "unsupported_unit")
        .when(~F.col("measured_date").between(F.lit(window.start), F.lit(window.end)), "outside_window")
    )
    return deduplicated.withColumn("reject_reason", reason)


register(Source("air_quality_hourly", read_bronze, to_silver))
