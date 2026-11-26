from datetime import date, datetime

import pytest

from urban_analytics.api_sources import (
    AIR_QUALITY_SCHEMA,
    OPENAQ_PAGE_SIZE,
    WEATHER_SCHEMA,
    OpenAqClient,
    OpenAqUnavailable,
    bronze_frame,
    fetch_air_quality,
    fetch_weather,
    utc_span,
)
from urban_analytics.platform import Window

WINDOW = Window(date(2024, 1, 1), date(2024, 1, 2))


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class FakeApi:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, dict(params or {}), dict(headers or {})))
        for suffix, responses in self.routes.items():
            if url.endswith(suffix):
                return responses.pop(0) if isinstance(responses, list) else responses(params)
        raise AssertionError(f"unexpected url {url}")


def weather_payload():
    return {
        "daily": {
            "time": ["2024-01-01", "2024-01-02"],
            "temperature_2m_max": [5.0, 6.0],
            "temperature_2m_min": [-1.0, 0.0],
            "temperature_2m_mean": [2.0, 3.0],
            "precipitation_sum": [0.0, 1.2],
            "rain_sum": [0.0, 1.2],
            "snowfall_sum": [0.0, 0.0],
            "wind_speed_10m_max": [12.0, 20.5],
        }
    }


def location(location_id, first, last, parameters):
    return {
        "id": location_id,
        "name": f"Station {location_id}",
        "coordinates": {"latitude": 40.7, "longitude": -74.0},
        "datetimeFirst": {"utc": first},
        "datetimeLast": {"utc": last},
        "sensors": [
            {"id": location_id * 10 + index, "parameter": {"name": name, "units": unit}}
            for index, (name, unit) in enumerate(parameters)
        ],
    }


def hour(stamp, value):
    return {
        "value": value,
        "period": {"datetimeFrom": {"utc": stamp}, "datetimeTo": {"utc": stamp.replace(":00:00Z", ":59:59Z")}},
    }


def test_weather_rows_are_renamed_and_typed():
    api = FakeApi({"/archive": [FakeResponse(weather_payload())]})
    rows = fetch_weather(WINDOW, get=api)
    assert rows[1] == {
        "weather_date": date(2024, 1, 2),
        "temperature_max_c": 6.0,
        "temperature_min_c": 0.0,
        "temperature_mean_c": 3.0,
        "precipitation_mm": 1.2,
        "rain_mm": 1.2,
        "snowfall_cm": 0.0,
        "wind_speed_max_kmh": 20.5,
    }
    assert api.calls[0][1]["timezone"] == "America/New_York"


def test_openaq_requires_a_key():
    with pytest.raises(ValueError):
        OpenAqClient("")


def test_openaq_backs_off_on_rate_limit_and_sends_the_key():
    waits = []
    api = FakeApi({"/locations": [FakeResponse({}, 429), FakeResponse({}, 429), FakeResponse({"results": []})]})
    client = OpenAqClient("secret", get=api, sleep=waits.append, pause_seconds=0)
    assert client.pages("locations", {}) == []
    assert [wait for wait in waits if wait] == [5, 10]
    assert all(headers["X-API-Key"] == "secret" for _, _, headers in api.calls)


def test_openaq_follows_pages_until_a_short_page():
    full_page = {"results": [hour("2024-01-01T00:00:00Z", 1.0)] * OPENAQ_PAGE_SIZE}
    api = FakeApi({"/hours": [FakeResponse(full_page), FakeResponse({"results": [hour("2024-01-01T01:00:00Z", 2.0)]})]})
    client = OpenAqClient("secret", get=api, sleep=lambda _: None, pause_seconds=0)
    assert len(client.pages("sensors/1/hours", {})) == OPENAQ_PAGE_SIZE + 1
    assert [params["page"] for _, params, _ in api.calls] == [1, 2]


def test_air_quality_keeps_active_stations_and_supported_parameters():
    locations = {
        "results": [
            location(1, "2020-01-01T00:00:00Z", "2025-01-01T00:00:00Z", [("pm25", "µg/m³"), ("pm10", "µg/m³")]),
            location(2, "2010-01-01T00:00:00Z", "2015-01-01T00:00:00Z", [("no2", "ppm")]),
        ]
    }
    api = FakeApi(
        {
            "/locations": [FakeResponse(locations)],
            "/sensors/10/hours": [FakeResponse({"results": [hour("2024-01-01T05:00:00Z", 7.5)]})],
        }
    )
    client = OpenAqClient("secret", get=api, sleep=lambda _: None, pause_seconds=0)
    rows = fetch_air_quality(client, WINDOW)
    assert rows == [
        {
            "location_id": 1,
            "location_name": "Station 1",
            "sensor_id": 10,
            "parameter": "pm25",
            "unit": "µg/m³",
            "latitude": 40.7,
            "longitude": -74.0,
            "value": 7.5,
            "datetime_from_utc": datetime(2024, 1, 1, 5),
            "datetime_to_utc": datetime(2024, 1, 1, 5, 59, 59),
        }
    ]
    hours_call = api.calls[-1][1]
    assert hours_call["datetime_from"] == "2023-12-31T00:00:00Z"
    assert hours_call["datetime_to"] == "2024-01-04T00:00:00Z"


def test_utc_span_covers_the_local_window_on_both_sides():
    start, end = utc_span(WINDOW)
    assert start == datetime(2023, 12, 31)
    assert end == datetime(2024, 1, 4)


def test_rows_match_the_bronze_schemas(spark):
    api = FakeApi({"/archive": [FakeResponse(weather_payload())]})
    weather = bronze_frame(spark, fetch_weather(WINDOW, get=api), WEATHER_SCHEMA)
    assert weather.count() == 2
    assert dict(weather.dtypes)["weather_date"] == "date"
    air = bronze_frame(
        spark,
        [
            {
                "location_id": 1,
                "location_name": "Station 1",
                "sensor_id": 10,
                "parameter": "no2",
                "unit": "ppm",
                "latitude": 40.7,
                "longitude": -74.0,
                "value": 0.02,
                "datetime_from_utc": datetime(2024, 1, 1, 5),
                "datetime_to_utc": datetime(2024, 1, 1, 6),
            }
        ],
        AIR_QUALITY_SCHEMA,
    )
    assert dict(air.dtypes)["datetime_from_utc"] == "timestamp"


def test_openaq_retries_server_errors():
    waits = []
    api = FakeApi({"/locations": [FakeResponse({}, 500), FakeResponse({}, 503), FakeResponse({"results": []})]})
    client = OpenAqClient("secret", get=api, sleep=waits.append, pause_seconds=0)
    assert client.pages("locations", {}) == []
    assert [wait for wait in waits if wait] == [5, 10]


def test_openaq_gives_up_after_repeated_server_errors():
    api = FakeApi({"/locations": lambda params: FakeResponse({}, 500)})
    client = OpenAqClient("secret", get=api, sleep=lambda _: None, pause_seconds=0)
    with pytest.raises(OpenAqUnavailable):
        client.pages("locations", {})


def test_air_quality_skips_a_sensor_that_keeps_failing():
    locations = {
        "results": [
            location(1, "2020-01-01T00:00:00Z", "2025-01-01T00:00:00Z", [("pm25", "µg/m³")]),
            location(2, "2020-01-01T00:00:00Z", "2025-01-01T00:00:00Z", [("no2", "ppm")]),
        ]
    }
    api = FakeApi(
        {
            "/locations": [FakeResponse(locations)],
            "/sensors/10/hours": lambda params: FakeResponse({}, 500),
            "/sensors/20/hours": [FakeResponse({"results": [hour("2024-01-01T05:00:00Z", 0.02)]})],
        }
    )
    client = OpenAqClient("secret", get=api, sleep=lambda _: None, pause_seconds=0)
    rows = fetch_air_quality(client, WINDOW)
    assert [row["sensor_id"] for row in rows] == [20]
