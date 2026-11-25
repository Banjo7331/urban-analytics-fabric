CREATE OR ALTER PROCEDURE dbo.LoadReportTables
AS
BEGIN
    DROP TABLE IF EXISTS dbo.RptDemandByHour;
    CREATE TABLE dbo.RptDemandByHour AS
    SELECT hour, avg_trips, avg_revenue_usd, avg_no2, avg_pm25
    FROM dbo.DemandByHourVersusPollution;

    DROP TABLE IF EXISTS dbo.RptRevenuePerTrip;
    CREATE TABLE dbo.RptRevenuePerTrip AS
    SELECT year, month, month_name, trips, revenue_per_trip_usd, revenue_per_trip_eur, avg_usd_per_eur, min_usd_per_eur, max_usd_per_eur
    FROM dbo.RevenuePerTripUsdVersusEur;

    DROP TABLE IF EXISTS dbo.RptZoneStationLinks;
    CREATE TABLE dbo.RptZoneStationLinks AS
    SELECT zone_name, borough, station_name, parameter, pearson_r, days, avg_daily_trips
    FROM dbo.StrongestZoneStationLinks;

    DROP TABLE IF EXISTS dbo.RptYearlyGrowth;
    CREATE TABLE dbo.RptYearlyGrowth AS
    SELECT year, trips, revenue_usd, avg_pm25, avg_no2, usa_gdp_year, usa_gdp_usd
    FROM dbo.YearlyGrowthVersusEnvironment;
END;
GO

EXEC dbo.LoadReportTables;
GO
