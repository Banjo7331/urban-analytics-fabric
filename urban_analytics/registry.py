import importlib
import pkgutil
from dataclasses import dataclass
from typing import Callable

from pyspark.sql import DataFrame, SparkSession

from urban_analytics.platform import Platform

BronzeReader = Callable[[SparkSession, Platform], DataFrame]
SilverTransform = Callable[[DataFrame, Platform], DataFrame]


@dataclass(frozen=True)
class Source:
    name: str
    read_bronze: BronzeReader
    to_silver: SilverTransform
    partition_by: tuple[str, ...] = ()


_registry: dict[str, Source] = {}


def register(source: Source) -> Source:
    _registry[source.name] = source
    return source


def registered_sources() -> dict[str, Source]:
    _discover()
    return dict(_registry)


def _discover() -> None:
    from urban_analytics import sources

    for module in pkgutil.iter_modules(sources.__path__):
        importlib.import_module(f"{sources.__name__}.{module.name}")
