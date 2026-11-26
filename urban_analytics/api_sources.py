import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Callable

import requests

from urban_analytics.platform import Window

NYC_LATITUDE = 40.7128
NYC_LONGITUDE = -74.0060
TIMEOUT_SECONDS = 60

OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
WEATHER_FIELDS = {
    "temperature_2m_max": "temperature_max_c",
    "temperature_2m_min": "temperature_min_c",
    "temperature_2m_mean": "temperature_mean_c",
    "precipitation_sum": "precipitation_mm",
    "rain_sum": "rain_mm",
    "snowfall_sum": "snowfall_cm",
    "wind_speed_10m_max": "wind_speed_max_kmh",
}
WEATHER_SCHEMA = "weather_date date, " + ", ".join(f"{name} double" for name in WEATHER_FIELDS.values())

OPENAQ_API = "https://api.openaq.org/v3"
OPENAQ_PARAMETERS = ("pm25", "no2", "o3")
OPENAQ_RADIUS_METERS = 25000
OPENAQ_PAGE_SIZE = 1000
OPENAQ_PAUSE_SECONDS = 1.1
OPENAQ_MAX_ATTEMPTS = 5
OPENAQ_BACKOFF_SECONDS = 5
OPENAQ_RETRYABLE_STATUS = (429, 500, 502, 503, 504)
AIR_QUALITY_SCHEMA = (
    "location_id long, location_name string, sensor_id long, parameter string, unit string, "
    "latitude double, longitude double, value double, datetime_from_utc timestamp, datetime_to_utc timestamp"
)

Get = Callable[..., requests.Response]


def fetch_json(get: Get, url: str, params: dict, headers: dict | None = None) -> dict:
    response = get(url, params=params, headers=headers or {}, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def weather_rows(payload: dict) -> list[dict]:
    daily = payload["daily"]
    columns = {target: daily[source] for source, target in WEATHER_FIELDS.items()}
    return [
        {"weather_date": date.fromisoformat(day), **{name: values[index] for name, values in columns.items()}}
        for index, day in enumerate(daily["time"])
    ]


def fetch_weather(window: Window, get: Get = requests.get) -> list[dict]:
    params = {
        "latitude": NYC_LATITUDE,
        "longitude": NYC_LONGITUDE,
        "start_date": window.start.isoformat(),
        "end_date": window.end.isoformat(),
        "daily": ",".join(WEATHER_FIELDS),
        "timezone": "America/New_York",
    }
    return weather_rows(fetch_json(get, OPEN_METEO_ARCHIVE, params))


def utc_naive(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True)
class Sensor:
    location_id: int
    location_name: str
    sensor_id: int
    parameter: str
    unit: str
    latitude: float
    longitude: float


class OpenAqUnavailable(RuntimeError):
    pass


class OpenAqClient:
    def __init__(
        self,
        api_key: str,
        get: Get = requests.get,
        sleep: Callable[[float], None] = time.sleep,
        pause_seconds: float = OPENAQ_PAUSE_SECONDS,
    ):
        if not api_key:
            raise ValueError("OpenAQ API key is required")
        self.headers = {"X-API-Key": api_key, "Accept": "application/json"}
        self.get = get
        self.sleep = sleep
        self.pause_seconds = pause_seconds

    def request(self, path: str, params: dict) -> dict:
        for attempt in range(OPENAQ_MAX_ATTEMPTS):
            self.sleep(self.pause_seconds)
            response = self.get(f"{OPENAQ_API}/{path}", params=params, headers=self.headers, timeout=TIMEOUT_SECONDS)
            if response.status_code not in OPENAQ_RETRYABLE_STATUS:
                response.raise_for_status()
                return response.json()
            self.sleep(OPENAQ_BACKOFF_SECONDS * 2**attempt)
        raise OpenAqUnavailable(f"OpenAQ returned {response.status_code} after {OPENAQ_MAX_ATTEMPTS} attempts: {path}")

    def pages(self, path: str, params: dict) -> list[dict]:
        results, page = [], 1
        while True:
            batch = self.request(path, params | {"limit": OPENAQ_PAGE_SIZE, "page": page})["results"]
            results.extend(batch)
            if len(batch) < OPENAQ_PAGE_SIZE:
                return results
            page += 1


def active_during(location: dict, start: datetime, end: datetime) -> bool:
    first = utc_naive((location.get("datetimeFirst") or {}).get("utc"))
    last = utc_naive((location.get("datetimeLast") or {}).get("utc"))
    return (first is None or first <= end) and (last is None or last >= start)


def sensors_in(locations: list[dict], start: datetime, end: datetime) -> list[Sensor]:
    return [
        Sensor(
            location["id"],
            location["name"],
            sensor["id"],
            sensor["parameter"]["name"],
            sensor["parameter"]["units"],
            location["coordinates"]["latitude"],
            location["coordinates"]["longitude"],
        )
        for location in locations
        if active_during(location, start, end)
        for sensor in location["sensors"]
        if sensor["parameter"]["name"] in OPENAQ_PARAMETERS
    ]


def hour_rows(sensor: Sensor, hours: list[dict]) -> list[dict]:
    return [
        {
            "location_id": sensor.location_id,
            "location_name": sensor.location_name,
            "sensor_id": sensor.sensor_id,
            "parameter": sensor.parameter,
            "unit": sensor.unit,
            "latitude": sensor.latitude,
            "longitude": sensor.longitude,
            "value": hour["value"],
            "datetime_from_utc": utc_naive(hour["period"]["datetimeFrom"]["utc"]),
            "datetime_to_utc": utc_naive(hour["period"]["datetimeTo"]["utc"]),
        }
        for hour in hours
    ]


def utc_span(window: Window) -> tuple[datetime, datetime]:
    start = datetime.combine(window.start - timedelta(days=1), datetime.min.time())
    end = datetime.combine(window.end + timedelta(days=2), datetime.min.time())
    return start, end


def fetch_air_quality(client: OpenAqClient, window: Window) -> list[dict]:
    start, end = utc_span(window)
    locations = client.pages(
        "locations",
        {"coordinates": f"{NYC_LATITUDE},{NYC_LONGITUDE}", "radius": OPENAQ_RADIUS_METERS},
    )
    span = {"datetime_from": f"{start.isoformat()}Z", "datetime_to": f"{end.isoformat()}Z"}
    rows = []
    for sensor in sensors_in(locations, start, end):
        try:
            hours = client.pages(f"sensors/{sensor.sensor_id}/hours", span)
        except OpenAqUnavailable as error:
            logging.warning("Skipping sensor %s: %s", sensor.sensor_id, error)
            continue
        rows.extend(hour_rows(sensor, hours))
    return rows


def bronze_frame(spark, rows: list[dict], schema: str):
    return spark.createDataFrame(rows, schema=schema)


def write_bronze(spark, rows: list[dict], table: str, schema: str, table_format: str = "delta") -> int:
    bronze_frame(spark, rows, schema).write.format(table_format).mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)
    return len(rows)
