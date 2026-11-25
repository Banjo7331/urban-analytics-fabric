import os
import time
from datetime import date

import pytest
from pyspark.sql import SparkSession

from tests import synthetic
from urban_analytics.gold import build_gold
from urban_analytics.platform import Window
from urban_analytics.silver import build_silver

WINDOW = Window(date(2024, 1, 1), date(2024, 2, 29))

os.environ["TZ"] = "UTC"
time.tzset()


@pytest.fixture(scope="session")
def spark(tmp_path_factory):
    warehouse = tmp_path_factory.mktemp("warehouse")
    session = (
        SparkSession.builder.master("local[2]")
        .appName("urban-analytics-tests")
        .config("spark.sql.warehouse.dir", str(warehouse))
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.ui.enabled", "false")
        .config("spark.driver.memory", "2g")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    yield session
    session.stop()


@pytest.fixture(scope="session")
def fixture(spark, tmp_path_factory):
    root = tmp_path_factory.mktemp("lakehouses")
    return synthetic.build(spark, str(root), WINDOW)


@pytest.fixture(scope="session")
def silver(spark, fixture):
    return {result.source: result for result in build_silver(spark, fixture.platform)}


@pytest.fixture(scope="session")
def gold(spark, fixture, silver):
    return {result.table: result for result in build_gold(spark, fixture.platform)}
