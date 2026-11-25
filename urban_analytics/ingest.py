from dataclasses import dataclass
from typing import BinaryIO, Callable

import requests

from urban_analytics.platform import Platform
from urban_analytics.sources.taxi_trips import file_name

TLC_BASE = "https://d37ci6vzurychx.cloudfront.net"
ZONES_URL = f"{TLC_BASE}/misc/taxi_zone_lookup.csv"
CHUNK_BYTES = 8 * 1024 * 1024

Sink = Callable[[str], BinaryIO]


@dataclass(frozen=True)
class Landed:
    url: str
    relative_path: str
    bytes: int


def copy_url(url: str, relative_path: str, open_sink: Sink) -> Landed:
    total = 0
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with open_sink(relative_path) as sink:
            for chunk in response.iter_content(CHUNK_BYTES):
                sink.write(chunk)
                total += len(chunk)
    return Landed(url, relative_path, total)


def taxi_targets(platform: Platform) -> list[tuple[str, str]]:
    targets = [(ZONES_URL, "taxi/zones/taxi_zone_lookup.csv")]
    for month in platform.window.months():
        name = file_name(month)
        targets.append((f"{TLC_BASE}/trip-data/{name}", f"taxi/yellow/{name}"))
    return targets


def land_taxi_files(platform: Platform, open_sink: Sink) -> list[Landed]:
    return [copy_url(url, relative_path, open_sink) for url, relative_path in taxi_targets(platform)]
