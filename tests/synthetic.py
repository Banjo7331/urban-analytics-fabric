import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from urban_analytics.platform import Platform, Window

SEED = 7
ROWS_PER_MONTH = 3000
STATIONS = [
    (1001, "Division Street", 40.714, -73.998),
    (1002, "Queens College", 40.736, -73.822),
    (1003, "IS 52", 40.816, -73.902),
    (1004, "Fresh Kills West", 40.580, -74.198),
]
PARAMETERS = {"pm25": "µg/m³", "no2": "ppm", "o3": "ppm"}
SIGNAL_ZONE = 161
SIGNAL_STATION = 1001
KNOWN_ZONES = {
    1: ("EWR", "Newark Airport", "EWR"),
    132: ("Queens", "JFK Airport", "Airports"),
    138: ("Queens", "LaGuardia Airport", "Airports"),
    161: ("Manhattan", "Midtown Center", "Yellow Zone"),
    236: ("Manhattan", "Upper East Side North", "Yellow Zone"),
    237: ("Manhattan", "Upper East Side South", "Yellow Zone"),
    264: ("Unknown", "NV", "N/A"),
    265: ("N/A", "Outside of NYC", "N/A"),
}
GDP_AGGREGATES = (("WLD", "World"), ("EUU", "European Union"))
LOCAL_UTC_OFFSET_HOURS = 5
BOROUGHS = ("Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island")


@dataclass
class TaxiDirt:
    duplicates: int = 20
    negative_fare: int = 15
    non_positive_duration: int = 10
    outside_window: int = 12
    unknown_pickup_zone: int = 8
    distance_over_limit: int = 6
    null_passengers: int = 5

    def rejected(self) -> int:
        return (
            self.negative_fare
            + self.non_positive_duration
            + self.outside_window
            + self.unknown_pickup_zone
            + self.distance_over_limit
        )


@dataclass
class AirDirt:
    negative_value: int = 30
    duplicates: int = 25
    unsupported_parameter: int = 10
    outside_window: int = 10


@dataclass
class Fixture:
    platform: Platform
    taxi_dirt: TaxiDirt = field(default_factory=TaxiDirt)
    air_dirt: AirDirt = field(default_factory=AirDirt)
    clean_trips: int = 0
    weekend_or_holiday_days: int = 0


def days_in(window: Window) -> list[date]:
    return [window.start + timedelta(days=offset) for offset in range((window.end - window.start).days + 1)]


def day_signal(day: date, window: Window) -> float:
    position = (day - window.start).days
    return float(np.sin(position / 6.0) + 1.5)


def taxi_month(month: str, window: Window, rng: np.random.Generator, dirt: TaxiDirt, passenger_dtype) -> pd.DataFrame:
    first = datetime.strptime(month, "%Y-%m")
    next_month = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    seconds = int((next_month - first).total_seconds())
    pickups = [first + timedelta(seconds=int(offset)) for offset in rng.integers(0, seconds, ROWS_PER_MONTH)]
    duration_minutes = rng.gamma(2.5, 6.0, ROWS_PER_MONTH).clip(1, 180)
    distance = (duration_minutes / 4.0 * rng.uniform(0.6, 1.4, ROWS_PER_MONTH)).round(2)
    fare = (3.0 + distance * 2.9).round(2)
    tip = (fare * rng.choice([0, 0.15, 0.2, 0.25], ROWS_PER_MONTH)).round(2)
    zones = rng.integers(1, 264, ROWS_PER_MONTH)
    signal_mask = rng.random(ROWS_PER_MONTH) < np.array(
        [0.18 * day_signal(p.date(), window) / 2.5 for p in pickups]
    )
    zones[signal_mask] = SIGNAL_ZONE
    passengers = rng.integers(1, 5, ROWS_PER_MONTH).astype(passenger_dtype)
    frame = pd.DataFrame(
        {
            "VendorID": rng.choice([1, 2], ROWS_PER_MONTH).astype("int32"),
            "tpep_pickup_datetime": pickups,
            "tpep_dropoff_datetime": [p + timedelta(minutes=float(m)) for p, m in zip(pickups, duration_minutes)],
            "passenger_count": passengers,
            "trip_distance": distance,
            "RatecodeID": np.ones(ROWS_PER_MONTH, dtype="int64"),
            "store_and_fwd_flag": np.where(rng.random(ROWS_PER_MONTH) < 0.01, "Y", "N"),
            "PULocationID": zones.astype("int32"),
            "DOLocationID": rng.integers(1, 264, ROWS_PER_MONTH).astype("int32"),
            "payment_type": rng.choice([1, 2], ROWS_PER_MONTH).astype("int64"),
            "fare_amount": fare,
            "extra": np.where(rng.random(ROWS_PER_MONTH) < 0.5, 1.0, 0.0),
            "mta_tax": np.full(ROWS_PER_MONTH, 0.5),
            "tip_amount": tip,
            "tolls_amount": np.where(rng.random(ROWS_PER_MONTH) < 0.05, 6.94, 0.0),
            "improvement_surcharge": np.full(ROWS_PER_MONTH, 1.0),
            "total_amount": 0.0,
            "congestion_surcharge": np.full(ROWS_PER_MONTH, 2.5),
            "Airport_fee": np.where(rng.random(ROWS_PER_MONTH) < 0.08, 1.75, 0.0),
        }
    )
    frame["total_amount"] = (
        frame["fare_amount"]
        + frame["extra"]
        + frame["mta_tax"]
        + frame["tip_amount"]
        + frame["tolls_amount"]
        + frame["improvement_surcharge"]
        + frame["congestion_surcharge"]
        + frame["Airport_fee"]
    ).round(2)
    return frame


def apply_taxi_dirt(frame: pd.DataFrame, dirt: TaxiDirt, window: Window) -> pd.DataFrame:
    frame = frame.copy()
    cursor = 0

    def take(count: int) -> slice:
        nonlocal cursor
        chosen = slice(cursor, cursor + count)
        cursor += count
        return chosen

    rows = take(dirt.negative_fare)
    frame.loc[frame.index[rows], "fare_amount"] = -5.0
    rows = take(dirt.non_positive_duration)
    frame.loc[frame.index[rows], "tpep_dropoff_datetime"] = frame.loc[frame.index[rows], "tpep_pickup_datetime"]
    rows = take(dirt.outside_window)
    frame.loc[frame.index[rows], "tpep_pickup_datetime"] = datetime(2008, 12, 31, 23, 0)
    frame.loc[frame.index[rows], "tpep_dropoff_datetime"] = datetime(2008, 12, 31, 23, 30)
    rows = take(dirt.unknown_pickup_zone)
    frame.loc[frame.index[rows], "PULocationID"] = 999
    rows = take(dirt.distance_over_limit)
    frame.loc[frame.index[rows], "trip_distance"] = 450.0
    duplicates = frame.iloc[cursor : cursor + dirt.duplicates]
    return pd.concat([frame, duplicates], ignore_index=True)


def apply_null_passengers(frame: pd.DataFrame, count: int) -> pd.DataFrame:
    frame = frame.copy()
    frame.loc[frame.index[:count], "passenger_count"] = np.nan
    return frame


def zones_frame() -> pd.DataFrame:
    rows = []
    for zone_id in range(1, 266):
        if zone_id in KNOWN_ZONES:
            borough, name, service = KNOWN_ZONES[zone_id]
        else:
            borough = BOROUGHS[zone_id % len(BOROUGHS)]
            name = f"Zone {zone_id}"
            service = "Yellow Zone" if borough == "Manhattan" else "Boro Zone"
        rows.append({"LocationID": zone_id, "Borough": borough, "Zone": name, "service_zone": service})
    return pd.DataFrame(rows)


def air_quality_frame(window: Window, rng: np.random.Generator, dirt: AirDirt) -> pd.DataFrame:
    rows = []
    for day in days_in(window):
        signal = day_signal(day, window)
        for hour in range(24):
            stamp = datetime(day.year, day.month, day.day, hour)
            for station_id, name, lat, lon in STATIONS:
                for index, (parameter, unit) in enumerate(PARAMETERS.items()):
                    base = {"pm25": 8.0, "no2": 0.02, "o3": 0.03}[parameter]
                    scale = {"pm25": 4.0, "no2": 0.01, "o3": 0.01}[parameter]
                    lift = signal * scale if station_id == SIGNAL_STATION else rng.uniform(0, scale)
                    rows.append(
                        {
                            "location_id": station_id,
                            "location_name": name,
                            "sensor_id": station_id * 10 + index,
                            "parameter": parameter,
                            "unit": unit,
                            "latitude": lat,
                            "longitude": lon,
                            "value": round(base + lift + rng.normal(0, scale * 0.1), 4),
                            "datetime_from_utc": stamp,
                            "datetime_to_utc": stamp + timedelta(hours=1),
                        }
                    )
    frame = pd.DataFrame(rows)
    frame.loc[frame.index[: dirt.negative_value], "value"] = -999.0
    start = dirt.negative_value
    frame.loc[frame.index[start : start + dirt.unsupported_parameter], "parameter"] = "pm10"
    start += dirt.unsupported_parameter
    outside = frame.iloc[start : start + dirt.outside_window].copy()
    outside["datetime_from_utc"] = [
        datetime(window.start.year - 1, 6, 1, hour) for hour in range(dirt.outside_window)
    ]
    outside["sensor_id"] = 99999
    duplicates = frame.iloc[start + dirt.outside_window : start + dirt.outside_window + dirt.duplicates]
    return pd.concat([frame, outside, duplicates], ignore_index=True)


def gdp_frame() -> pd.DataFrame:
    rows = []
    for code, name, base in (("USA", "United States", 2.1e13), ("DEU", "Germany", 3.9e12), ("POL", "Poland", 6.5e11)):
        for year in range(2015, 2024):
            rows.append({"country_code": code, "country_name": name, "year": year, "gdp_usd": base * (1.03 ** (year - 2015))})
    frame = pd.DataFrame(rows)
    frame.loc[[2, 11, 20], "gdp_usd"] = None
    aggregates = pd.DataFrame(
        [{"country_code": code, "country_name": name, "year": 2023, "gdp_usd": 1.0e14} for code, name in GDP_AGGREGATES]
    )
    return pd.concat([frame, frame.iloc[[0, 9]], aggregates], ignore_index=True)


def fx_frame(window: Window, rng: np.random.Generator) -> tuple[pd.DataFrame, int]:
    rows = []
    missing = 0
    for day in days_in(window):
        if day.weekday() >= 5 or (day.month == 1 and day.day == 1):
            missing += 1
            continue
        rows.append({"rate_date": day, "usd_per_eur": round(1.08 + rng.normal(0, 0.01), 4)})
    frame = pd.DataFrame(rows)
    frame.loc[0, "usd_per_eur"] = None
    return pd.concat([frame, frame.iloc[[3]]], ignore_index=True), missing + 1


def weather_frame(window: Window, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for day in days_in(window):
        mean = rng.normal(2.0, 4.0)
        rows.append(
            {
                "weather_date": day,
                "temperature_max_c": round(mean + 4, 1),
                "temperature_min_c": round(mean - 4, 1),
                "temperature_mean_c": round(mean, 1),
                "precipitation_mm": round(max(0.0, rng.normal(1.5, 3.0)), 1),
                "rain_mm": 0.0,
                "snowfall_cm": round(max(0.0, rng.normal(0, 1.0)), 1),
                "wind_speed_max_kmh": round(abs(rng.normal(20, 8)), 1),
            }
        )
    frame = pd.DataFrame(rows)
    outside = frame.iloc[[0]].copy()
    outside["weather_date"] = window.start - timedelta(days=40)
    return pd.concat([frame, outside, frame.iloc[[1, 2]]], ignore_index=True)


def build(spark, root: str, window: Window) -> Fixture:
    rng = np.random.default_rng(SEED)
    platform = Platform.local(root, window)
    fixture = Fixture(platform)

    yellow_dir = platform.bronze.files("taxi", "yellow")
    zones_dir = platform.bronze.files("taxi", "zones")
    os.makedirs(yellow_dir, exist_ok=True)
    os.makedirs(zones_dir, exist_ok=True)

    months = window.months()
    for index, month in enumerate(months):
        frame = taxi_month(month, window, rng, fixture.taxi_dirt, "int64" if index == 0 else "float64")
        if index == 0:
            frame = apply_taxi_dirt(frame, fixture.taxi_dirt, window)
        else:
            frame = apply_null_passengers(frame, fixture.taxi_dirt.null_passengers)
        frame.to_parquet(f"{yellow_dir}/yellow_tripdata_{month}.parquet", index=False)
    fixture.clean_trips = ROWS_PER_MONTH * len(months) - fixture.taxi_dirt.rejected()
    zones_frame().to_csv(f"{zones_dir}/taxi_zone_lookup.csv", index=False)

    for database in ("lh_bronze", "lh_silver", "lh_gold"):
        spark.sql(f"CREATE DATABASE IF NOT EXISTS {database}")

    fx, fixture.weekend_or_holiday_days = fx_frame(window, rng)
    bronze_tables = {
        "openaq_hourly": air_quality_frame(window, rng, fixture.air_dirt),
        "worldbank_gdp": gdp_frame(),
        "ecb_fx_usd_eur": fx,
        "openmeteo_daily": weather_frame(window, rng),
    }
    for name, frame in bronze_tables.items():
        spark.createDataFrame(frame).write.mode("overwrite").saveAsTable(platform.bronze.table(name))
    return fixture
