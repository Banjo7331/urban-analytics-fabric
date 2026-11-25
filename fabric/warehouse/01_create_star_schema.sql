CREATE TABLE dbo.DimDate (
    date_key int NOT NULL,
    full_date date NOT NULL,
    year int NOT NULL,
    quarter int NOT NULL,
    month int NOT NULL,
    month_name varchar(20) NOT NULL,
    day int NOT NULL,
    day_of_week int NOT NULL,
    day_name varchar(20) NOT NULL,
    week_of_year int NOT NULL,
    is_weekend bit NOT NULL
);

CREATE TABLE dbo.DimZone (
    zone_key int NOT NULL,
    borough varchar(50) NOT NULL,
    zone_name varchar(100) NOT NULL,
    service_zone varchar(50) NOT NULL,
    is_airport bit NOT NULL
);

CREATE TABLE dbo.DimStation (
    station_key int NOT NULL,
    station_name varchar(200) NOT NULL,
    latitude float NOT NULL,
    longitude float NOT NULL
);

CREATE TABLE dbo.DimFx (
    date_key int NOT NULL,
    full_date date NOT NULL,
    usd_per_eur float NOT NULL,
    eur_per_usd float NOT NULL,
    is_carried_forward bit NOT NULL
);

CREATE TABLE dbo.DimGdp (
    country_code varchar(3) NOT NULL,
    country_name varchar(200) NOT NULL,
    year int NOT NULL,
    gdp_usd float NOT NULL
);

CREATE TABLE dbo.FactTaxiDaily (
    date_key int NOT NULL,
    pickup_zone_key int NOT NULL,
    trips int NOT NULL,
    passengers int NULL,
    distance_miles decimal(18, 2) NOT NULL,
    fare_usd decimal(18, 2) NOT NULL,
    tip_usd decimal(18, 2) NOT NULL,
    revenue_usd decimal(18, 2) NOT NULL,
    revenue_eur decimal(18, 2) NULL,
    avg_trip_minutes decimal(18, 2) NOT NULL
);

CREATE TABLE dbo.FactTaxiHourly (
    date_key int NOT NULL,
    hour int NOT NULL,
    trips int NOT NULL,
    revenue_usd decimal(18, 2) NOT NULL,
    avg_trip_minutes decimal(18, 2) NOT NULL,
    avg_distance_miles decimal(18, 2) NOT NULL
);

CREATE TABLE dbo.FactAirQualityDaily (
    date_key int NOT NULL,
    station_key int NOT NULL,
    parameter varchar(10) NOT NULL,
    unit varchar(20) NULL,
    avg_value float NOT NULL,
    min_value float NOT NULL,
    max_value float NOT NULL,
    samples int NOT NULL
);

CREATE TABLE dbo.FactAirQualityHourly (
    date_key int NOT NULL,
    hour int NOT NULL,
    parameter varchar(10) NOT NULL,
    avg_value float NOT NULL,
    samples int NOT NULL
);

CREATE TABLE dbo.FactUrbanDaily (
    date_key int NOT NULL,
    full_date date NOT NULL,
    is_weekend bit NOT NULL,
    trips int NULL,
    revenue_usd decimal(18, 2) NULL,
    revenue_eur decimal(18, 2) NULL,
    avg_distance_miles decimal(18, 2) NULL,
    avg_pm25 float NULL,
    avg_no2 float NULL,
    avg_o3 float NULL,
    temperature_mean_c float NULL,
    temperature_max_c float NULL,
    precipitation_mm float NULL,
    snowfall_cm float NULL,
    wind_speed_max_kmh float NULL,
    usd_per_eur float NULL
);

CREATE TABLE dbo.FactZoneStationCorrelation (
    zone_key int NOT NULL,
    station_key int NOT NULL,
    parameter varchar(10) NOT NULL,
    pearson_r float NOT NULL,
    days int NOT NULL,
    avg_daily_trips float NOT NULL
);

ALTER TABLE dbo.DimDate ADD CONSTRAINT PK_DimDate PRIMARY KEY NONCLUSTERED (date_key) NOT ENFORCED;
ALTER TABLE dbo.DimZone ADD CONSTRAINT PK_DimZone PRIMARY KEY NONCLUSTERED (zone_key) NOT ENFORCED;
ALTER TABLE dbo.DimStation ADD CONSTRAINT PK_DimStation PRIMARY KEY NONCLUSTERED (station_key) NOT ENFORCED;
ALTER TABLE dbo.DimFx ADD CONSTRAINT PK_DimFx PRIMARY KEY NONCLUSTERED (date_key) NOT ENFORCED;
ALTER TABLE dbo.DimGdp ADD CONSTRAINT PK_DimGdp PRIMARY KEY NONCLUSTERED (country_code, year) NOT ENFORCED;
ALTER TABLE dbo.FactTaxiDaily ADD CONSTRAINT PK_FactTaxiDaily PRIMARY KEY NONCLUSTERED (date_key, pickup_zone_key) NOT ENFORCED;
ALTER TABLE dbo.FactTaxiHourly ADD CONSTRAINT PK_FactTaxiHourly PRIMARY KEY NONCLUSTERED (date_key, hour) NOT ENFORCED;
ALTER TABLE dbo.FactAirQualityDaily ADD CONSTRAINT PK_FactAirQualityDaily PRIMARY KEY NONCLUSTERED (date_key, station_key, parameter) NOT ENFORCED;
ALTER TABLE dbo.FactAirQualityHourly ADD CONSTRAINT PK_FactAirQualityHourly PRIMARY KEY NONCLUSTERED (date_key, hour, parameter) NOT ENFORCED;
ALTER TABLE dbo.FactUrbanDaily ADD CONSTRAINT PK_FactUrbanDaily PRIMARY KEY NONCLUSTERED (date_key) NOT ENFORCED;
ALTER TABLE dbo.FactZoneStationCorrelation ADD CONSTRAINT PK_FactZoneStationCorrelation PRIMARY KEY NONCLUSTERED (zone_key, station_key, parameter) NOT ENFORCED;

ALTER TABLE dbo.FactTaxiDaily ADD CONSTRAINT FK_FactTaxiDaily_DimDate FOREIGN KEY (date_key) REFERENCES dbo.DimDate (date_key) NOT ENFORCED;
ALTER TABLE dbo.FactTaxiDaily ADD CONSTRAINT FK_FactTaxiDaily_DimZone FOREIGN KEY (pickup_zone_key) REFERENCES dbo.DimZone (zone_key) NOT ENFORCED;
ALTER TABLE dbo.FactTaxiDaily ADD CONSTRAINT FK_FactTaxiDaily_DimFx FOREIGN KEY (date_key) REFERENCES dbo.DimFx (date_key) NOT ENFORCED;
ALTER TABLE dbo.FactTaxiHourly ADD CONSTRAINT FK_FactTaxiHourly_DimDate FOREIGN KEY (date_key) REFERENCES dbo.DimDate (date_key) NOT ENFORCED;
ALTER TABLE dbo.FactAirQualityDaily ADD CONSTRAINT FK_FactAirQualityDaily_DimDate FOREIGN KEY (date_key) REFERENCES dbo.DimDate (date_key) NOT ENFORCED;
ALTER TABLE dbo.FactAirQualityDaily ADD CONSTRAINT FK_FactAirQualityDaily_DimStation FOREIGN KEY (station_key) REFERENCES dbo.DimStation (station_key) NOT ENFORCED;
ALTER TABLE dbo.FactAirQualityHourly ADD CONSTRAINT FK_FactAirQualityHourly_DimDate FOREIGN KEY (date_key) REFERENCES dbo.DimDate (date_key) NOT ENFORCED;
ALTER TABLE dbo.FactUrbanDaily ADD CONSTRAINT FK_FactUrbanDaily_DimDate FOREIGN KEY (date_key) REFERENCES dbo.DimDate (date_key) NOT ENFORCED;
ALTER TABLE dbo.FactZoneStationCorrelation ADD CONSTRAINT FK_FactZoneStationCorrelation_DimZone FOREIGN KEY (zone_key) REFERENCES dbo.DimZone (zone_key) NOT ENFORCED;
ALTER TABLE dbo.FactZoneStationCorrelation ADD CONSTRAINT FK_FactZoneStationCorrelation_DimStation FOREIGN KEY (station_key) REFERENCES dbo.DimStation (station_key) NOT ENFORCED;
