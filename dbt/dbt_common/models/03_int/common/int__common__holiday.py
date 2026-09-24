import holidays
import pandas as pd


def model(dbt, _session):
    dbt.config(enabled=True, materialized="table", packages=["holidays"])
    # ISO 3166-1 alpha-2 code from the `holiday_country` var (dbt_project.yml of dbt_common).
    country_holidays = holidays.country_holidays(dbt.config.get("holiday_country") or "NL")

    df_dates = dbt.ref("int__common__date").select("DATE")
    df = df_dates.to_pandas()

    print("Original DataFrame schema and sample data:")
    print(df.dtypes)
    print(df.head())

    # Ensure DATE column is in the correct format
    if "DATE" in df.columns:
        df["DATE"] = pd.to_datetime(df["DATE"])
    else:
        raise ValueError("Expected column 'DATE' not found.")

    # The holiday name per date, None when the date is not a holiday
    df["HOLIDAY_NAME"] = df["DATE"].apply(country_holidays.get)

    # Filter dataframe to keep only rows containing a holiday name
    df = df[df["HOLIDAY_NAME"].notnull()]

    # If 'DATE_TIME' exists and needs conversion
    if "DATE_TIME" in df.columns:
        df["DATE_TIME"] = df["DATE_TIME"].astype("datetime64[ns]")  # Convert to nanoseconds
        print("DATE_TIME column successfully converted to timestamp[ns]")

    print("Final DataFrame schema and sample data:")
    print(df.dtypes)
    print(df.head())

    # Return final dataset (Pandas DataFrame)
    return df
