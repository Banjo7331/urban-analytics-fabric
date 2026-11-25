from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Lakehouse:
    name: str
    files_root: str

    def files(self, *parts: str) -> str:
        return "/".join((self.files_root.rstrip("/"), *parts))

    def table(self, name: str) -> str:
        return f"{self.name}.{name}"


@dataclass(frozen=True)
class Window:
    start: date
    end: date

    def months(self) -> list[str]:
        result = []
        year, month = self.start.year, self.start.month
        while (year, month) <= (self.end.year, self.end.month):
            result.append(f"{year:04d}-{month:02d}")
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        return result


@dataclass(frozen=True)
class Platform:
    bronze: Lakehouse
    silver: Lakehouse
    gold: Lakehouse
    window: Window
    table_format: str = "delta"

    @classmethod
    def fabric(cls, workspace: str, window: Window) -> "Platform":
        onelake = f"abfss://{workspace}@onelake.dfs.fabric.microsoft.com"

        def lakehouse(name: str) -> Lakehouse:
            return Lakehouse(name, f"{onelake}/{name}.Lakehouse/Files")

        return cls(lakehouse("lh_bronze"), lakehouse("lh_silver"), lakehouse("lh_gold"), window)

    @classmethod
    def local(cls, root: str, window: Window, table_format: str = "parquet") -> "Platform":
        def lakehouse(name: str) -> Lakehouse:
            return Lakehouse(name, f"{root}/{name}/Files")

        return cls(lakehouse("lh_bronze"), lakehouse("lh_silver"), lakehouse("lh_gold"), window, table_format)
