CREATE OR ALTER PROCEDURE dbo.LoadReportTables
AS
BEGIN
    DELETE FROM dbo.RptDemandByHour;
    INSERT INTO dbo.RptDemandByHour (hour, avg_trips, avg_revenue_usd, avg_no2, avg_pm25)
    SELECT hour, avg_trips, avg_revenue_usd, avg_no2, avg_pm25
    FROM dbo.DemandByHourVersusPollution;

    DELETE FROM dbo.RptRevenuePerTrip;
    INSERT INTO dbo.RptRevenuePerTrip (year, month, month_name, trips, revenue_per_trip_usd, revenue_per_trip_eur, avg_usd_per_eur, min_usd_per_eur, max_usd_per_eur)
    SELECT year, month, month_name, trips, revenue_per_trip_usd, revenue_per_trip_eur, avg_usd_per_eur, min_usd_per_eur, max_usd_per_eur
    FROM dbo.RevenuePerTripUsdVersusEur;

    DELETE FROM dbo.RptZoneStationLinks;
    INSERT INTO dbo.RptZoneStationLinks (zone_name, borough, station_name, parameter, pearson_r, days, avg_daily_trips)
    SELECT zone_name, borough, station_name, parameter, pearson_r, days, avg_daily_trips
    FROM dbo.StrongestZoneStationLinks;

    DELETE FROM dbo.RptYearlyGrowth;
    INSERT INTO dbo.RptYearlyGrowth (year, trips, revenue_usd, avg_pm25, avg_no2, usa_gdp_year, usa_gdp_usd)
    SELECT year, trips, revenue_usd, avg_pm25, avg_no2, usa_gdp_year, usa_gdp_usd
    FROM dbo.YearlyGrowthVersusEnvironment;
END;
GO