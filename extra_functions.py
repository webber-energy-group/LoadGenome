import pandas as pd


def percentage_of_whole(df, value_column, group_by_column):
    """Creates dictionary where keys are values in group_by_column and values are
    percentage of total of value column

    Args:
        df (pandas.DataFrame): Contains data to be used
        value_column (string): column containing values to find percentage of whole
        group_by_column (string): column containing values to group by
    """
    sum_df = pd.DataFrame(df.groupby(group_by_column)[value_column].sum())
    out = pd.DataFrame(sum_df[value_column] / sum_df[value_column].sum()).to_dict()[
        value_column
    ]

    return out


def process_county_region_mapping(county_data, region_column):
    """Adds columns to county_data that contain the percentage of each county's
    percent population of each region in region column"""
    county_data[region_column + "_group_percent"] = percentage_of_whole_for_each(
        county_data, "population", region_column
    )

    pop_percent = percentage_of_whole(county_data, "population", region_column)

    county_data[region_column + "_total_percent"] = county_data[
        region_column + "_group_percent"
    ] * county_data[region_column].map(pop_percent)

    return county_data


# def EV_load_by_model_region(load_zones, ev_data, county_regions):
#     # Finding the total population of ERCOT
#     NON_LOAD = county_regions[county_regions.cdr_zone.isin(["non-load", "none"])]
#     ERCOT_pop = sum(county_regions["population_2018"]) - sum(
#         NON_LOAD["population_2018"]
#     )

#     # Find load per county
#     cdr_zone_dict = {
#         "non-load": "none",
#         "none": "none",
#         "coast": "COAST",
#         "east": "EAST",
#         "far west": "FWEST",
#         "north": "NORTH",
#         "north central": "NCENT",
#         "south": "SOUTH",
#         "south central": "SCENT",
#         "west": "WEST",
#     }
#     COUNTY_LOADS = pd.DataFrame()
#     check = []
#     for i in range(len(county_regions)):
#         county = county_regions.iloc[i]["county"]
#         cdr_zone = county_regions.iloc[i]["cdr_zone"]
#         population = county_regions.iloc[i]["population_2018"]
#         cdr_zone = cdr_zone_dict[cdr_zone]
#         if cdr_zone == "none":
#             COUNTY_PERCENTAGE_OF_LOAD = 0
#             COUNTY_LOADS[county] = 0
#         else:
#             COUNTY_PERCENTAGE_OF_LOAD = population / ERCOT_pop
#             COUNTY_LOADS[county] = ev_data * float(COUNTY_PERCENTAGE_OF_LOAD)
#         check.append(COUNTY_PERCENTAGE_OF_LOAD)
#     COUNTY_LOADS.fillna(0, inplace=True)

#     # Aggregate load per county into load per model region
#     REGION_LOADS = pd.DataFrame()
#     for i in range(len(load_zones)):
#         zone = load_zones[i]
#         sum_of_loads = []
#         for j in range(len(county_regions)):
#             county = county_regions.iloc[j]["county"]
#             if county_regions.iloc[j]["model_region"] == zone:
#                 if len(sum_of_loads) == 0:
#                     sum_of_loads = COUNTY_LOADS[county]
#                 else:
#                     sum_of_loads = [
#                         x + y for x, y in zip(sum_of_loads, COUNTY_LOADS[county])
#                     ]
#         REGION_LOADS[zone] = sum_of_loads

#     return REGION_LOADS


def separate_date_time(df):
    """Separates DataFrame with datetime column into Year, Month, Day, and Period columns

    Args:
        df (pandas.DataFrame): DataFrame with column named "datetime" containing datetime objects

    Returns:
        pandas.DataFrame: DataFrame with separate columns for Year, Month, Day, and Period
    """

    df["Year"] = [d.year for d in df["date_time"]]
    df["Month"] = [d.month for d in df["date_time"]]
    df["Day"] = [d.day for d in df["date_time"]]
    df["Period"] = [d.hour for d in df["date_time"]]
    df = df.drop(columns=["date_time"])

    # Rearrange columns
    cols = df.columns.tolist()
    cols = cols[-4:] + cols[:-4]
    df = df[cols]

    return df


def ERCOT_hour_ending_to_datetime(base_profile):
    """Gets timeseries of ERCOT load profile, does something with adjusting for DST
    TODO Document or prove necessity of this function

    Args:
        base_profile (pandas.DataFrame): load profile

    Returns:
        pandas.DataFrame: DataFrame with separate columns for Year, Month, Day, and Period
    """
    date_time = pd.DataFrame()

    times = base_profile["Hour Ending"]
    times7 = times.copy()
    times2 = []

    for i in range(len(times)):
        if "DST" in times[i]:
            times[i] = times[i].replace("DST", "")
        for j in range(1, 10):
            hour_check = " 0%s:" % str(j)
            hour_new = " 0%s:" % str(j - 1)
            if hour_check in times[i]:
                times2.append(times[i].replace(hour_check, hour_new))
        for j in range(10, 11):
            hour_check = " %s:" % str(j)
            hour_new = " 0%s:" % str(j - 1)
            if hour_check in times[i]:
                times2.append(times[i].replace(hour_check, hour_new))
        for j in range(11, 25):
            hour_check = " %s:" % str(j)
            hour_new = " %s:" % str(j - 1)
            if hour_check in times[i]:
                times2.append(times[i].replace(hour_check, hour_new))

    date_time["date_time"] = pd.to_datetime(times2, infer_datetime_format=True)
    date_time = separate_date_time(date_time)

    return date_time


def set_tz(q):
    return q.tz_localize("America/Chicago", ambiguous=True)
