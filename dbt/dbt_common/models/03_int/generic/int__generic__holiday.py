import holidays
import pandas as pd


def get_holiday_name(date_col):
    # Netherlands holidays
    dutch_holidays = holidays.Netherlands()
    # Return the name of the holiday if it exists, otherwise return None
    return dutch_holidays.get(date_col)


def model(dbt, _session):
    dbt.config(enabled=True, materialized="table", packages=["holidays"])

    df_dates = dbt.ref("int__generic__date").select("DATE")
    df = df_dates.to_pandas()

    print("Original DataFrame schema and sample data:")
    print(df.dtypes)
    print(df.head())

    # Ensure DATE column is in the correct format
    if "DATE" in df.columns:
        df["DATE"] = pd.to_datetime(df["DATE"])
    else:
        raise ValueError("Expected column 'DATE' not found.")

    # Apply function to get holiday names
    df["HOLIDAY_NAME"] = df["DATE"].apply(get_holiday_name)

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
