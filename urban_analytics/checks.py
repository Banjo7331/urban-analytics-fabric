from pyspark.sql import Column
from pyspark.sql import functions as F


def missing_number(column: str) -> Column:
    return F.col(column).isNull() | F.isnan(column)
