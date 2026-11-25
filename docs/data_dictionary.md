# Data dictionary

Columns of every silver and gold table.

## Silver (lh_silver)

Every silver source also has a `<table>_rejected` companion with the same columns plus `reject_reason`.

### air_quality_hourly

One row per sensor and hour from OpenAQ, limited to PM2.5, NO2 and O3.

| Column | Type | Meaning |
|---|---|---|
| station_id | int | OpenAQ location id |
| station_name | string | OpenAQ location name |
| sensor_id | int | OpenAQ sensor id |
| parameter | string | pm25, no2 or o3 |
| source_unit | string | unit as reported by the provider |
| latitude | double | station latitude |
| longitude | double | station longitude |
| source_value | double | value as reported by the provider |
| measured_at_utc | timestamp | start of the hourly period, UTC |
| value | double | measured value in µg/m³; NO2 and O3 converted from ppm or ppb at 25 °C |
| unit | string | µg/m³ for every parameter after conversion |
| measured_at | timestamp | start of the hourly period, New York local time |
| measured_date | date | date part of measured_at |
| measured_hour | int | hour of measured_at |

### fx_rates_daily

ECB reference rate, US dollars per euro, business days only.

| Column | Type | Meaning |
|---|---|---|
| rate_date | date | ECB reference date |
| usd_per_eur | double | US dollars for one euro |

### gdp_annual

World Bank GDP in current US dollars, one row per country and year.

| Column | Type | Meaning |
|---|---|---|
| country_code | string | ISO 3166-1 alpha-3 |
| country_name | string | country name from World Bank |
| year | int | calendar year |
| gdp_usd | double | GDP in current US dollars |

### taxi_trips

One row per accepted yellow-taxi trip. Partitioned by pickup_month; the partition is the unit of overwrite.

| Column | Type | Meaning |
|---|---|---|
| vendor_id | int | TLC vendor code (1 or 2) |
| pickup_at | timestamp | trip start, UTC as published by TLC |
| dropoff_at | timestamp | trip end |
| passenger_count | int | passengers as entered by the driver, may be null |
| trip_distance_miles | double | meter distance in miles |
| rate_code_id | int | TLC rate code |
| store_and_forward | string | Y when the record was held in vehicle memory before sending |
| pickup_zone_id | int | TLC zone of pickup |
| dropoff_zone_id | int | TLC zone of dropoff |
| payment_type | int | 1 card, 2 cash, 3 no charge, 4 dispute |
| fare_usd | double | meter fare |
| extra_usd | double | rush hour and overnight extras |
| mta_tax_usd | double | MTA tax |
| tip_usd | double | tip, card payments only |
| tolls_usd | double | tolls |
| improvement_surcharge_usd | double | improvement surcharge |
| total_usd | double | total charged |
| congestion_surcharge_usd | double | congestion surcharge |
| airport_fee_usd | double | airport pickup fee |
| source_file | string | bronze file the row came from |
| pickup_date | date | date part of pickup_at |
| pickup_hour | int | hour of pickup, 0 to 23 |
| trip_minutes | double | dropoff minus pickup in minutes |
| pickup_month | string | yyyy-MM, partition column |

### taxi_zones

TLC taxi zone lookup, one row per LocationID (1 to 265).

| Column | Type | Meaning |
|---|---|---|
| zone_id | int | TLC LocationID |
| borough | string | borough name |
| zone_name | string | zone name |
| service_zone | string | Yellow Zone, Boro Zone, Airports, EWR or N/A |

### weather_daily

Open-Meteo daily archive for the NYC coordinates.

| Column | Type | Meaning |
|---|---|---|
| weather_date | date | calendar day |
| temperature_max_c | double | daily maximum air temperature, Celsius |
| temperature_min_c | double | daily minimum air temperature |
| temperature_mean_c | double | daily mean air temperature |
| precipitation_mm | double | total precipitation |
| rain_mm | double | rain only |
| snowfall_cm | double | snowfall |
| wind_speed_max_kmh | double | maximum wind speed |

## Gold (lh_gold, mirrored into wh_analytics)

### dim_date

Calendar covering the processing window, one row per day.

| Column | Type | Meaning |
|---|---|---|
| date_key | int | yyyyMMdd as integer |
| full_date | date | calendar date |
| year | int | calendar year |
| quarter | int | 1 to 4 |
| month | int | 1 to 12 |
| month_name | string | English month name |
| day | int | day of month |
| day_of_week | int | 1 Monday to 7 Sunday |
| day_name | string | English day name |
| week_of_year | int | ISO week number |
| is_weekend | boolean | Saturday or Sunday |

### dim_zone

Taxi zones with borough and an airport flag.

| Column | Type | Meaning |
|---|---|---|
| zone_key | int | TLC LocationID |
| borough | string | borough name |
| zone_name | string | zone name |
| service_zone | string | Yellow Zone, Boro Zone, Airports, EWR or N/A |
| is_airport | boolean | service zone is Airports |

### dim_station

Air quality stations with coordinates, latest name wins.

| Column | Type | Meaning |
|---|---|---|
| station_key | int | OpenAQ location id |
| station_name | string | OpenAQ location name |
| latitude | double | station latitude |
| longitude | double | station longitude |

### dim_fx

Daily exchange rate with weekends and holidays filled from the previous business day.

| Column | Type | Meaning |
|---|---|---|
| date_key | int | yyyyMMdd as integer |
| full_date | date | calendar date |
| usd_per_eur | double | US dollars for one euro |
| eur_per_usd | double | 1 / usd_per_eur |
| is_carried_forward | boolean | true when the day had no ECB fixing and the previous one was reused |

### dim_gdp

GDP per country and year.

| Column | Type | Meaning |
|---|---|---|
| country_code | string | ISO 3166-1 alpha-3 |
| country_name | string | country name from World Bank |
| year | int | calendar year |
| gdp_usd | double | GDP in current US dollars |

### fact_taxi_daily

Grain: pickup date and pickup zone.

| Column | Type | Meaning |
|---|---|---|
| date_key | int | yyyyMMdd as integer |
| pickup_zone_key | int | TLC LocationID of pickup |
| trips | bigint | number of trips |
| passengers | bigint | sum of passenger_count |
| distance_miles | double | sum of trip distances |
| fare_usd | double | meter fare |
| tip_usd | double | tip, card payments only |
| revenue_usd | double | sum of total_usd |
| revenue_eur | double | revenue_usd converted at the day's rate |
| avg_trip_minutes | double | mean trip duration |

### fact_taxi_hourly

Grain: pickup date and hour, whole city.

| Column | Type | Meaning |
|---|---|---|
| date_key | int | yyyyMMdd as integer |
| hour | int | hour of day in New York local time, 0 to 23 |
| trips | bigint | number of trips |
| revenue_usd | double | sum of total_usd |
| avg_trip_minutes | double | mean trip duration |
| avg_distance_miles | double | mean trip distance |

### fact_air_quality_daily

Grain: date, station and pollutant.

| Column | Type | Meaning |
|---|---|---|
| date_key | int | yyyyMMdd as integer |
| station_key | int | OpenAQ location id |
| parameter | string | pm25, no2 or o3 |
| unit | string | µg/m³ for every parameter after conversion |
| avg_value | double | mean measured value |
| min_value | double | minimum measured value |
| max_value | double | maximum measured value |
| samples | bigint | number of hourly measurements aggregated |

### fact_air_quality_hourly

Grain: date, hour and pollutant, averaged over stations.

| Column | Type | Meaning |
|---|---|---|
| date_key | int | yyyyMMdd as integer |
| hour | int | hour of day in New York local time, 0 to 23 |
| parameter | string | pm25, no2 or o3 |
| avg_value | double | mean measured value |
| samples | bigint | number of hourly measurements aggregated |

### fact_urban_daily

Cross-domain mart, grain: date. Joins trips, pollution, weather and the exchange rate on one calendar.

| Column | Type | Meaning |
|---|---|---|
| date_key | int | yyyyMMdd as integer |
| full_date | date | calendar date |
| is_weekend | boolean | Saturday or Sunday |
| trips | bigint | number of trips |
| revenue_usd | double | sum of total_usd |
| revenue_eur | double | revenue_usd converted at the day's rate |
| avg_distance_miles | double | mean trip distance |
| avg_pm25 | double | city mean PM2.5 across stations |
| avg_no2 | double | city mean NO2 across stations |
| avg_o3 | double | city mean O3 across stations |
| temperature_mean_c | double | daily mean air temperature |
| temperature_max_c | double | daily maximum air temperature, Celsius |
| precipitation_mm | double | total precipitation |
| snowfall_cm | double | snowfall |
| wind_speed_max_kmh | double | maximum wind speed |
| usd_per_eur | double | US dollars for one euro |

### fact_zone_station_correlation

Pearson correlation between a zone's daily trips and a station's daily pollutant level, over at least 20 shared days.

| Column | Type | Meaning |
|---|---|---|
| zone_key | int | TLC LocationID |
| station_key | int | OpenAQ location id |
| parameter | string | pm25, no2 or o3 |
| pearson_r | double | Pearson correlation coefficient |
| days | bigint | number of shared days used |
| avg_daily_trips | double | mean daily trips in the zone over the shared days |

## Warehouse naming

The warehouse mirrors every gold table under a PascalCase name (`fact_taxi_daily` becomes `dbo.FactTaxiDaily`) with the same column names, money columns as `decimal(18,2)` and counts as `int`. Primary and foreign keys are declared `NOT ENFORCED`, which is what Fabric Warehouse supports and what Power BI needs to infer relationships.

## Reject reasons

| Table | Reason | Rule |
|---|---|---|
| taxi_trips | missing_timestamp | pickup or dropoff is null |
| taxi_trips | non_positive_duration | dropoff is not after pickup |
| taxi_trips | duration_over_24h | trip longer than 24 hours |
| taxi_trips | outside_window | pickup date outside the processing window, which also catches the 2008 timestamps TLC publishes |
| taxi_trips | negative_distance, distance_over_limit | distance below 0 or above 200 miles |
| taxi_trips | negative_fare, negative_total | refunds and corrections recorded as negatives |
| taxi_trips | unknown_pickup_zone, unknown_dropoff_zone | zone outside 1 to 265 |
| air_quality_hourly | missing_value, negative_value | null or sentinel values such as -999 |
| air_quality_hourly | unsupported_parameter | pollutant other than PM2.5, NO2, O3 |
| air_quality_hourly | outside_window | measurement outside the processing window |
| gdp_annual | invalid_country_code, missing_year, missing_value, non_positive_value | |
| fx_rates_daily | missing_date, missing_value, non_positive_rate | |
| weather_daily | missing_date, missing_temperature, inverted_temperature_range, negative_precipitation, outside_window | |
