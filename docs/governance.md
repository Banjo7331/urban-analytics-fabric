# Governance

## Naming

| Item | Convention | Example |
|---|---|---|
| Lakehouses | `lh_<layer>` | `lh_silver` |
| Warehouse | `wh_<purpose>` | `wh_analytics` |
| Lakehouse tables and columns | snake_case, unit in the name | `fare_usd`, `temperature_mean_c` |
| Warehouse tables | `Dim` / `Fact` / `Rpt` + PascalCase | `FactTaxiDaily` |
| Rejected rows | `<table>_rejected` | `taxi_trips_rejected` |
| Notebooks | two-digit order prefix | `02_build_silver` |

## Layer rules

- Bronze is a raw copy and is only replaced by re-running the same ingestion.
- Silver never drops a row silently: it is either accepted or written to `_rejected` with a reason.
- Gold is rebuilt from silver on every run.
- The warehouse only copies gold; no business logic lives there except the report views.

## Time and units

- Air quality is converted from UTC to `America/New_York` in silver so it lines up with taxi pickups, which TLC publishes in local time.
- All pollutants are stored in µg/m³; the original value and unit are kept in `source_value` and `source_unit`.

## Personal data

None. TLC trips contain zones, not locations or driver ids; the other sources are public statistics.

## Access

| Role | Access |
|---|---|
| Data engineer | workspace Admin or Member |
| Analyst | workspace Viewer, read on `wh_analytics` |
| Business user | report only |

Row-level security: role `Borough` on the semantic model with the filter `DimZone[borough] = "Manhattan"` (one role per borough).

## Secrets

The OpenAQ key is never stored in code. The pipeline passes it to the notebook as a SecureString parameter with secure input enabled; the notebook can also read it from Azure Key Vault.

## Refresh

`daily_refresh` runs once a day. Re-running is safe: taxi files are overwritten, API tables replaced, silver and gold rebuilt.
