let
    Indicator = "NY.GDP.MKTP.CD",
    Result = let
            response = Json.Document(
                Web.Contents(
                    "https://api.worldbank.org",
                    [RelativePath = "v2/country/all/indicator/" & Indicator, Query = [format = "json", per_page = "20000"]]
                )
            ),
            observations = Table.FromList(response{1}, Splitter.SplitByNothing(), {"observation"}),
            expanded = Table.ExpandRecordColumn(
                observations,
                "observation",
                {"countryiso3code", "country", "date", "value"},
                {"country_code", "country", "year", "gdp_usd"}
            ),
            country = Table.ExpandRecordColumn(expanded, "country", {"value"}, {"country_name"}),
            typed = Table.TransformColumnTypes(
                country,
                {{"country_code", type text}, {"country_name", type text}, {"year", Int64.Type}, {"gdp_usd", type number}}
            ),
            selected = Table.SelectColumns(typed, {"country_code", "country_name", "year", "gdp_usd"})
        in
            selected
in
    Result
