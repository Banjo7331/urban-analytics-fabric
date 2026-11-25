import pytest
from pyspark.sql import functions as F

from tests import synthetic
from urban_analytics.registry import registered_sources
from urban_analytics.silver import rejected_table

EXPECTED_SOURCES = {"taxi_trips", "taxi_zones", "air_quality_hourly", "gdp_annual", "fx_rates_daily", "weather_daily"}


def reasons(spark, table) -> dict[str, int]:
    rows = spark.table(table).groupBy("reject_reason").count().collect()
    return {row["reject_reason"]: row["count"] for row in rows}


def test_registry_discovers_every_source():
    assert set(registered_sources()) == EXPECTED_SOURCES


def test_taxi_trips_rejects_each_injected_defect_exactly_once(spark, fixture, silver):
    dirt = fixture.taxi_dirt
    found = reasons(spark, fixture.platform.silver.table(rejected_table("taxi_trips")))
    assert found == {
        "negative_fare": dirt.negative_fare,
        "non_positive_duration": dirt.non_positive_duration,
        "outside_window": dirt.outside_window,
        "unknown_pickup_zone": dirt.unknown_pickup_zone,
        "distance_over_limit": dirt.distance_over_limit,
    }
    assert silver["taxi_trips"].accepted == fixture.clean_trips
    assert silver["taxi_trips"].rejected == dirt.rejected()


def test_taxi_trips_reconciles_schemas_across_monthly_files(spark, fixture, silver):
    trips = spark.table(fixture.platform.silver.table("taxi_trips"))
    assert dict(trips.dtypes)["passenger_count"] == "int"
    assert trips.filter(F.col("passenger_count").isNull()).count() == fixture.taxi_dirt.null_passengers
    assert set(row["source_file"] for row in trips.select("source_file").distinct().collect()) == {
        "yellow_tripdata_2024-01.parquet",
        "yellow_tripdata_2024-02.parquet",
    }


def test_taxi_trips_is_partitioned_by_month_and_has_no_duplicates(spark, fixture, silver):
    trips = spark.table(fixture.platform.silver.table("taxi_trips"))
    assert set(row["pickup_month"] for row in trips.select("pickup_month").distinct().collect()) == {"2024-01", "2024-02"}
    trip_columns = [column for column in trips.columns if column != "source_file"]
    assert trips.dropDuplicates(trip_columns).count() == trips.count()


def test_taxi_zones_cover_the_full_tlc_range(spark, fixture, silver):
    zones = spark.table(fixture.platform.silver.table("taxi_zones"))
    assert zones.count() == 265
    assert zones.filter(F.col("zone_id") == 132).first()["zone_name"] == "JFK Airport"


def first_local_hours_before_window() -> int:
    rows_per_hour = len(synthetic.STATIONS) * len(synthetic.PARAMETERS)
    return synthetic.LOCAL_UTC_OFFSET_HOURS * rows_per_hour


def test_air_quality_rejects_sentinels_duplicates_and_unsupported_parameters(spark, fixture, silver):
    dirt = fixture.air_dirt
    found = reasons(spark, fixture.platform.silver.table(rejected_table("air_quality_hourly")))
    spill = first_local_hours_before_window() - dirt.negative_value - dirt.unsupported_parameter
    assert found == {
        "negative_value": dirt.negative_value,
        "unsupported_parameter": dirt.unsupported_parameter,
        "outside_window": dirt.outside_window + spill,
    }
    expected_clean = len(synthetic.days_in(fixture.platform.window)) * 24 * len(synthetic.STATIONS) * len(synthetic.PARAMETERS)
    assert silver["air_quality_hourly"].accepted == expected_clean - first_local_hours_before_window()


def test_air_quality_converts_gases_to_micrograms(spark, fixture, silver):
    measurements = spark.table(fixture.platform.silver.table("air_quality_hourly"))
    assert {row["unit"] for row in measurements.select("unit").distinct().collect()} == {"µg/m³"}
    no2 = measurements.filter(F.col("parameter") == "no2").select("source_value", "value").first()
    assert no2["value"] == pytest.approx(no2["source_value"] * 1881.6, rel=1e-3)
    pm25 = measurements.filter(F.col("parameter") == "pm25").select("source_value", "value").first()
    assert pm25["value"] == pytest.approx(pm25["source_value"], abs=1e-3)


def test_air_quality_uses_new_york_local_time(spark, fixture, silver):
    measurements = spark.table(fixture.platform.silver.table("air_quality_hourly"))
    row = measurements.filter(F.hour("measured_at_utc") == 12).select("measured_hour", "measured_date").first()
    assert row["measured_hour"] in (7, 8)
    earliest = measurements.agg(F.min("measured_at")).first()[0]
    assert earliest.date() == fixture.platform.window.start


def test_gdp_drops_missing_values_duplicates_and_regional_aggregates(spark, fixture, silver):
    assert silver["gdp_annual"].accepted == 3 * 9 - 3
    found = reasons(spark, fixture.platform.silver.table(rejected_table("gdp_annual")))
    assert found == {"missing_value": 3, "regional_aggregate": len(synthetic.GDP_AGGREGATES)}


def test_fx_keeps_one_row_per_business_day(spark, fixture, silver):
    rates = spark.table(fixture.platform.silver.table("fx_rates_daily"))
    assert rates.groupBy("rate_date").count().filter(F.col("count") > 1).count() == 0
    assert silver["fx_rates_daily"].rejected == 1


def test_weather_keeps_one_row_per_day_inside_window(spark, fixture, silver):
    assert silver["weather_daily"].accepted == len(synthetic.days_in(fixture.platform.window))
    assert silver["weather_daily"].rejected == 1
