from dataclasses import dataclass

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from urban_analytics.platform import Platform
from urban_analytics.registry import Source, registered_sources
from urban_analytics.tables import save

REJECT_COLUMN = "reject_reason"


@dataclass(frozen=True)
class SilverResult:
    source: str
    accepted: int
    rejected: int


def rejected_table(source_name: str) -> str:
    return f"{source_name}_rejected"


def split(df: DataFrame) -> tuple[DataFrame, DataFrame]:
    accepted = df.filter(F.col(REJECT_COLUMN).isNull()).drop(REJECT_COLUMN)
    rejected = df.filter(F.col(REJECT_COLUMN).isNotNull())
    return accepted, rejected


def build_source(spark: SparkSession, platform: Platform, source: Source) -> SilverResult:
    bronze = source.read_bronze(spark, platform)
    silver = source.to_silver(bronze, platform).cache()
    accepted, rejected = split(silver)
    save(accepted, platform.silver.table(source.name), platform.table_format, source.partition_by)
    save(rejected, platform.silver.table(rejected_table(source.name)), platform.table_format)
    result = SilverResult(source.name, accepted.count(), rejected.count())
    silver.unpersist()
    return result


def build_silver(spark: SparkSession, platform: Platform, only: tuple[str, ...] = ()) -> list[SilverResult]:
    selected = [
        source for name, source in registered_sources().items() if not only or name in only
    ]
    return [build_source(spark, platform, source) for source in selected]
