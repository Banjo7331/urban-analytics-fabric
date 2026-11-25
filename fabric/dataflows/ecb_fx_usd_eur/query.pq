let
    StartDate = "2024-01-01",
    EndDate = "2024-06-30",
    Result = let
            csv = Csv.Document(
                Web.Contents(
                    "https://data-api.ecb.europa.eu",
                    [
                        RelativePath = "service/data/EXR/D.USD.EUR.SP00.A",
                        Query = [format = "csvdata", startPeriod = StartDate, endPeriod = EndDate]
                    ]
                ),
                [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
            ),
            headers = Table.PromoteHeaders(csv, [PromoteAllScalars = true]),
            selected = Table.SelectColumns(headers, {"TIME_PERIOD", "OBS_VALUE"}),
            renamed = Table.RenameColumns(selected, {{"TIME_PERIOD", "rate_date"}, {"OBS_VALUE", "usd_per_eur"}}),
            typed = Table.TransformColumnTypes(renamed, {{"rate_date", type date}, {"usd_per_eur", type number}}, "en-US")
        in
            typed
in
    Result
