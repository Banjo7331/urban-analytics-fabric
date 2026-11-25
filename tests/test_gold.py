from pyspark.sql import functions as F

from tests import synthetic
from urban_analytics.gold import build_gold
from urban_analytics.silver import build_silver

GOLD_TABLES = {
    "dim_date",
    "dim_zone",
    "dim_station",
    "dim_fx",
    "dim_gdp",
    "fact_taxi_daily",
    "fact_taxi_hourly",
    "fact_air_quality_daily",
    "fact_air_quality_hourly",
    "fact_urban_daily",
    "fact_zone_station_correlation",
}


def table(spark, fixture, name):
    return spark.table(fixture.platform.gold.table(name))


def test_gold_builds_the_whole_star_schema(gold):
    assert set(gold) == GOLD_TABLES


def test_dim_date_covers_every_day_of_the_window(spark, fixture, gold):
    days = len(synthetic.days_in(fixture.platform.window))
    dates = table(spark, fixture, "dim_date")
    assert dates.count() == days
    first = dates.orderBy("date_key").first()
    assert first["date_key"] == 20240101 and first["day_name"] == "Monday" and first["day_of_week"] == 1
    assert dates.filter("is_weekend").count() == 16


def test_dim_fx_fills_every_calendar_day_and_marks_the_carried_rows(spark, fixture, gold):
    fx = table(spark, fixture, "dim_fx")
    assert fx.count() == len(synthetic.days_in(fixture.platform.window))
    assert fx.filter(F.col("usd_per_eur").isNull()).count() == 0
    assert fx.filter("is_carried_forward").count() == fixture.weekend_or_holiday_days
    assert fx.filter(F.abs(F.col("usd_per_eur") * F.col("eur_per_usd") - 1) > 1e-9).count() == 0


def test_fact_taxi_daily_preserves_every_accepted_trip(spark, fixture, silver, gold):
    daily = table(spark, fixture, "fact_taxi_daily")
    assert daily.agg(F.sum("trips")).first()[0] == silver["taxi_trips"].accepted
    assert daily.groupBy("date_key", "pickup_zone_key").count().filter("count > 1").count() == 0
    assert daily.filter(F.col("revenue_eur").isNull()).count() == 0
    fx = table(spark, fixture, "dim_fx")
    checked = daily.join(fx, "date_key").withColumn("expected", F.round(F.col("revenue_usd") / F.col("usd_per_eur"), 2))
    assert checked.filter(F.abs(F.col("expected") - F.col("revenue_eur")) > 0.011).count() == 0


def test_fact_taxi_hourly_matches_the_daily_total(spark, fixture, gold):
    hourly = table(spark, fixture, "fact_taxi_hourly")
    daily = table(spark, fixture, "fact_taxi_daily")
    assert hourly.agg(F.sum("trips")).first()[0] == daily.agg(F.sum("trips")).first()[0]
    assert hourly.select("hour").distinct().count() == 24


def test_fact_air_quality_daily_has_one_row_per_station_parameter_day(spark, fixture, silver, gold):
    daily = table(spark, fixture, "fact_air_quality_daily")
    assert daily.groupBy("date_key", "station_key", "parameter").count().filter("count > 1").count() == 0
    assert daily.agg(F.sum("samples")).first()[0] == silver["air_quality_hourly"].accepted
    assert daily.filter(F.col("min_value") > F.col("avg_value")).count() == 0


def test_fact_urban_daily_joins_all_domains_on_one_calendar(spark, fixture, gold):
    urban = table(spark, fixture, "fact_urban_daily")
    assert urban.count() == len(synthetic.days_in(fixture.platform.window))
    for column in ("trips", "revenue_eur", "avg_pm25", "avg_no2", "temperature_mean_c", "usd_per_eur"):
        assert urban.filter(F.col(column).isNull()).count() == 0, column


def test_correlation_recovers_the_planted_signal(spark, fixture, gold):
    correlations = table(spark, fixture, "fact_zone_station_correlation")
    planted = correlations.filter(
        (F.col("zone_key") == synthetic.SIGNAL_ZONE)
        & (F.col("station_key") == synthetic.SIGNAL_STATION)
        & (F.col("parameter") == "pm25")
    ).first()
    assert planted is not None
    assert planted["pearson_r"] > 0.6
    assert planted["days"] == len(synthetic.days_in(fixture.platform.window))


def test_rebuilding_both_layers_is_idempotent(spark, fixture, silver, gold):
    before = {name: table(spark, fixture, name).count() for name in GOLD_TABLES}
    again = {result.source: result for result in build_silver(spark, fixture.platform)}
    rebuilt = {result.table: result.rows for result in build_gold(spark, fixture.platform)}
    assert {name: result.accepted for name, result in again.items()} == {
        name: result.accepted for name, result in silver.items()
    }
    assert rebuilt == before
