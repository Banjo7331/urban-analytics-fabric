from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from urban_analytics.checks import missing_number
from urban_analytics.platform import Platform
from urban_analytics.registry import Source, register
from urban_analytics.tables import load

BRONZE_TABLE = "worldbank_gdp"
AGGREGATE_CODES = (
    "AFE", "AFW", "ARB", "CEB", "CSS", "EAP", "EAR", "EAS", "ECA", "ECS", "EMU", "EUU", "FCS", "HIC", "HPC",
    "IBD", "IBT", "IDA", "IDB", "IDX", "INX", "LAC", "LCN", "LDC", "LIC", "LMC", "LMY", "LTE", "MEA", "MIC",
    "MNA", "NAC", "OED", "OSS", "PRE", "PSS", "PST", "SAS", "SSA", "SSF", "SST", "TEA", "TEC", "TLA", "TMN",
    "TSA", "TSS", "UMC", "WLD",
)


def read_bronze(spark: SparkSession, platform: Platform) -> DataFrame:
    return load(spark, platform.bronze.table(BRONZE_TABLE))


def to_silver(df: DataFrame, platform: Platform) -> DataFrame:
    gdp = df.select(
        F.upper(F.trim("country_code")).alias("country_code"),
        F.trim("country_name").alias("country_name"),
        F.col("year").cast("int").alias("year"),
        F.col("gdp_usd").cast("double").alias("gdp_usd"),
    )
    reason = (
        F.when(F.col("country_code").isNull() | (F.length("country_code") != 3), "invalid_country_code")
        .when(F.col("country_code").isin(*AGGREGATE_CODES), "regional_aggregate")
        .when(F.col("year").isNull(), "missing_year")
        .when(missing_number("gdp_usd"), "missing_value")
        .when(F.col("gdp_usd") <= 0, "non_positive_value")
    )
    return gdp.dropDuplicates(["country_code", "year"]).withColumn("reject_reason", reason)


register(Source("gdp_annual", read_bronze, to_silver))
