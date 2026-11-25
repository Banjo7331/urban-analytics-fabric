from pyspark.sql import DataFrame, SparkSession


def save(df: DataFrame, table: str, table_format: str, partition_by: tuple[str, ...] = ()) -> None:
    writer = df.write.format(table_format).mode("overwrite")
    if partition_by:
        writer = writer.partitionBy(*partition_by).option("partitionOverwriteMode", "dynamic")
    else:
        writer = writer.option("overwriteSchema", "true")
    writer.saveAsTable(table)


def load(spark: SparkSession, table: str) -> DataFrame:
    return spark.table(table)
