from typing import Any

import holidays
import pandas as pd


def model(dbt: Any, _session: Any) -> pd.DataFrame:
    # Both imports have to be declared: Snowpark only installs the packages named here.
    dbt.config(enabled=True, materialized="table", packages=["holidays", "pandas"])
    # ISO 3166-1 alpha-2 code from the `holiday_country` meta config (dbt_project.yml of the installing project).
    # A statement of its own: dbt only passes meta keys whose dbt.config.meta_get() its parser finds, and it
    # misses a meta_get() inside an `or` in another call's arguments.
    country = dbt.config.meta_get("holiday_country", "NL")
    country_holidays = holidays.country_holidays(country)

    df = dbt.ref("int__common__date").select("DATE").to_pandas()
    df["DATE"] = pd.to_datetime(df["DATE"])

    # The holiday name per date, None when the date is not a holiday
    df["HOLIDAY_NAME"] = df["DATE"].apply(country_holidays.get)

    # Only the dates that are a holiday
    return df[df["HOLIDAY_NAME"].notnull()]
