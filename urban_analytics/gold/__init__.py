from dataclasses import dataclass

from pyspark.sql import SparkSession

from urban_analytics.gold import dimensions, facts
from urban_analytics.platform import Platform
from urban_analytics.tables import save


@dataclass(frozen=True)
class GoldResult:
    table: str
    rows: int


def build_gold(spark: SparkSession, platform: Platform) -> list[GoldResult]:
    dates = dimensions.dim_date(spark, platform).cache()
    fx = dimensions.dim_fx(spark, platform).cache()
    taxi_daily = facts.fact_taxi_daily(spark, platform, fx).cache()
    air_quality_daily = facts.fact_air_quality_daily(spark, platform).cache()

    tables = {
        "dim_date": dates,
        "dim_zone": dimensions.dim_zone(spark, platform),
        "dim_station": dimensions.dim_station(spark, platform),
        "dim_fx": fx,
        "dim_gdp": dimensions.dim_gdp(spark, platform),
        "fact_taxi_daily": taxi_daily,
        "fact_taxi_hourly": facts.fact_taxi_hourly(spark, platform),
        "fact_air_quality_daily": air_quality_daily,
        "fact_air_quality_hourly": facts.fact_air_quality_hourly(spark, platform),
        "fact_urban_daily": facts.fact_urban_daily(spark, platform, dates, taxi_daily, air_quality_daily, fx),
        "fact_zone_station_correlation": facts.fact_zone_station_correlation(taxi_daily, air_quality_daily),
    }

    results = []
    for name, df in tables.items():
        save(df, platform.gold.table(name), platform.table_format)
        results.append(GoldResult(name, spark.table(platform.gold.table(name)).count()))
    for cached in (dates, fx, taxi_daily, air_quality_daily):
        cached.unpersist()
    return results
