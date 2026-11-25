CREATE OR ALTER PROCEDURE dbo.LoadGold
AS
BEGIN
    DELETE FROM dbo.DimDate;
    INSERT INTO dbo.DimDate (date_key, full_date, year, quarter, month, month_name, day, day_of_week, day_name, week_of_year, is_weekend)
    SELECT date_key, full_date, year, quarter, month, month_name, day, day_of_week, day_name, week_of_year, is_weekend
    FROM lh_gold.dbo.dim_date;

    DELETE FROM dbo.DimZone;
    INSERT INTO dbo.DimZone (zone_key, borough, zone_name, service_zone, is_airport)
    SELECT zone_key, borough, zone_name, service_zone, is_airport
    FROM lh_gold.dbo.dim_zone;

    DELETE FROM dbo.DimStation;
    INSERT INTO dbo.DimStation (station_key, station_name, latitude, longitude)
    SELECT station_key, station_name, latitude, longitude
    FROM lh_gold.dbo.dim_station;

    DELETE FROM dbo.DimFx;
    INSERT INTO dbo.DimFx (date_key, full_date, usd_per_eur, eur_per_usd, is_carried_forward)
    SELECT date_key, full_date, usd_per_eur, eur_per_usd, is_carried_forward
    FROM lh_gold.dbo.dim_fx;

    DELETE FROM dbo.DimGdp;
    INSERT INTO dbo.DimGdp (country_code, country_name, year, gdp_usd)
    SELECT country_code, country_name, year, gdp_usd
    FROM lh_gold.dbo.dim_gdp;

    DELETE FROM dbo.FactTaxiDaily;
    INSERT INTO dbo.FactTaxiDaily (date_key, pickup_zone_key, trips, passengers, distance_miles, fare_usd, tip_usd, revenue_usd, revenue_eur, avg_trip_minutes)
    SELECT
        date_key,
        pickup_zone_key,
        CAST(trips AS int),
        CAST(passengers AS int),
        CAST(distance_miles AS decimal(18, 2)),
        CAST(fare_usd AS decimal(18, 2)),
        CAST(tip_usd AS decimal(18, 2)),
        CAST(revenue_usd AS decimal(18, 2)),
        CAST(revenue_eur AS decimal(18, 2)),
        CAST(avg_trip_minutes AS decimal(18, 2))
    FROM lh_gold.dbo.fact_taxi_daily;

    DELETE FROM dbo.FactTaxiHourly;
    INSERT INTO dbo.FactTaxiHourly (date_key, hour, trips, revenue_usd, avg_trip_minutes, avg_distance_miles)
    SELECT
        date_key,
        hour,
        CAST(trips AS int),
        CAST(revenue_usd AS decimal(18, 2)),
        CAST(avg_trip_minutes AS decimal(18, 2)),
        CAST(avg_distance_miles AS decimal(18, 2))
    FROM lh_gold.dbo.fact_taxi_hourly;

    DELETE FROM dbo.FactAirQualityDaily;
    INSERT INTO dbo.FactAirQualityDaily (date_key, station_key, parameter, unit, avg_value, min_value, max_value, samples)
    SELECT date_key, station_key, parameter, unit, avg_value, min_value, max_value, CAST(samples AS int)
    FROM lh_gold.dbo.fact_air_quality_daily;

    DELETE FROM dbo.FactAirQualityHourly;
    INSERT INTO dbo.FactAirQualityHourly (date_key, hour, parameter, avg_value, samples)
    SELECT date_key, hour, parameter, avg_value, CAST(samples AS int)
    FROM lh_gold.dbo.fact_air_quality_hourly;

    DELETE FROM dbo.FactUrbanDaily;
    INSERT INTO dbo.FactUrbanDaily (date_key, full_date, is_weekend, trips, revenue_usd, revenue_eur, avg_distance_miles, avg_pm25, avg_no2, avg_o3, temperature_mean_c, temperature_max_c, precipitation_mm, snowfall_cm, wind_speed_max_kmh, usd_per_eur)
    SELECT
        date_key,
        full_date,
        is_weekend,
        CAST(trips AS int),
        CAST(revenue_usd AS decimal(18, 2)),
        CAST(revenue_eur AS decimal(18, 2)),
        CAST(avg_distance_miles AS decimal(18, 2)),
        avg_pm25,
        avg_no2,
        avg_o3,
        temperature_mean_c,
        temperature_max_c,
        precipitation_mm,
        snowfall_cm,
        wind_speed_max_kmh,
        usd_per_eur
    FROM lh_gold.dbo.fact_urban_daily;

    DELETE FROM dbo.FactZoneStationCorrelation;
    INSERT INTO dbo.FactZoneStationCorrelation (zone_key, station_key, parameter, pearson_r, days, avg_daily_trips)
    SELECT zone_key, station_key, parameter, pearson_r, CAST(days AS int), avg_daily_trips
    FROM lh_gold.dbo.fact_zone_station_correlation;
END;
