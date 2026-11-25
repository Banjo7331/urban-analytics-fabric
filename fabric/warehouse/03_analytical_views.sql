CREATE VIEW dbo.TrafficVersusAirQuality AS
SELECT
    u.full_date,
    d.day_name,
    u.is_weekend,
    u.trips,
    u.avg_pm25,
    u.avg_no2,
    u.avg_o3,
    u.temperature_mean_c,
    u.precipitation_mm
FROM dbo.FactUrbanDaily AS u
JOIN dbo.DimDate AS d ON d.date_key = u.date_key;
GO

CREATE VIEW dbo.StrongestZoneStationLinks AS
SELECT
    z.zone_name,
    z.borough,
    s.station_name,
    c.parameter,
    c.pearson_r,
    c.days,
    c.avg_daily_trips
FROM dbo.FactZoneStationCorrelation AS c
JOIN dbo.DimZone AS z ON z.zone_key = c.zone_key
JOIN dbo.DimStation AS s ON s.station_key = c.station_key;
GO

CREATE VIEW dbo.DemandByHourVersusPollution AS
SELECT
    t.hour,
    AVG(CAST(t.trips AS float)) AS avg_trips,
    AVG(t.revenue_usd) AS avg_revenue_usd,
    AVG(CASE WHEN a.parameter = 'no2' THEN a.avg_value END) AS avg_no2,
    AVG(CASE WHEN a.parameter = 'pm25' THEN a.avg_value END) AS avg_pm25
FROM dbo.FactTaxiHourly AS t
LEFT JOIN dbo.FactAirQualityHourly AS a ON a.date_key = t.date_key AND a.hour = t.hour
GROUP BY t.hour;
GO

CREATE VIEW dbo.RevenuePerTripUsdVersusEur AS
SELECT
    d.year,
    d.month,
    d.month_name,
    SUM(f.trips) AS trips,
    SUM(f.revenue_usd) / SUM(f.trips) AS revenue_per_trip_usd,
    SUM(f.revenue_eur) / SUM(f.trips) AS revenue_per_trip_eur,
    AVG(x.usd_per_eur) AS avg_usd_per_eur,
    MIN(x.usd_per_eur) AS min_usd_per_eur,
    MAX(x.usd_per_eur) AS max_usd_per_eur
FROM dbo.FactTaxiDaily AS f
JOIN dbo.DimDate AS d ON d.date_key = f.date_key
JOIN dbo.DimFx AS x ON x.date_key = f.date_key
GROUP BY d.year, d.month, d.month_name;
GO

CREATE VIEW dbo.YearlyGrowthVersusEnvironment AS
WITH yearly AS (
    SELECT
        d.year,
        SUM(u.trips) AS trips,
        SUM(u.revenue_usd) AS revenue_usd,
        AVG(u.avg_pm25) AS avg_pm25,
        AVG(u.avg_no2) AS avg_no2
    FROM dbo.FactUrbanDaily AS u
    JOIN dbo.DimDate AS d ON d.date_key = u.date_key
    GROUP BY d.year
),
latest_gdp AS (
    SELECT y.year, MAX(g.year) AS gdp_year
    FROM yearly AS y
    JOIN dbo.DimGdp AS g ON g.country_code = 'USA' AND g.year <= y.year
    GROUP BY y.year
)
SELECT
    y.year,
    y.trips,
    y.revenue_usd,
    y.avg_pm25,
    y.avg_no2,
    l.gdp_year AS usa_gdp_year,
    g.gdp_usd AS usa_gdp_usd
FROM yearly AS y
LEFT JOIN latest_gdp AS l ON l.year = y.year
LEFT JOIN dbo.DimGdp AS g ON g.country_code = 'USA' AND g.year = l.gdp_year;
GO
