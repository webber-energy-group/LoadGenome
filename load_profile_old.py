"""
 This is a script to format raw ERCOT load profiles into the format desired for GenX modeling
"""

# Import packages
import pandas as pd
import numpy as np
from datetime import datetime

from warnings import simplefilter

simplefilter(action="ignore", category=pd.errors.PerformanceWarning)

pd.options.mode.chained_assignment = None


# Write function
def load_by_model_region(LOAD_ZONES, ERCOT_DATA, COUNTY_REGIONS):

    # Convert ERCOT Date to Year/Month/Day/Period
    def separate_date_time(df):
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

    def ERCOT_hour_ending_to_datetime(ERCOT_DATA):
        date_time = pd.DataFrame()
        if year == 2020:
            times = ERCOT_DATA["HourEnding"]
        elif year == 2021:
            times = ERCOT_DATA["Hour Ending"]
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

    date_time = ERCOT_hour_ending_to_datetime(ERCOT_DATA)

    ERCOT_DATA = date_time.merge(ERCOT_DATA, left_index=True, right_index=True)

    if year == 2020:
        ERCOT_DATA.drop(["HourEnding"], axis=1, inplace=True)
    elif year == 2021:
        ERCOT_DATA.drop(["Hour Ending"], axis=1, inplace=True)

    # Finding the total population of ERCOT
    NON_LOAD = COUNTY_REGIONS[COUNTY_REGIONS.cdr_zone.isin(["non-load", "none"])]
    ERCOT_pop = sum(COUNTY_REGIONS["population_2018"]) - sum(
        NON_LOAD["population_2018"]
    )

    # Find load per county
    COUNTY_LOADS = date_time.copy()

    cdr_zone_dict = {
        "non-load": "none",
        "none": "none",
        "coast": "COAST",
        "east": "EAST",
        "far west": "FWEST",
        "north": "NORTH",
        "north central": "NCENT",
        "south": "SOUTH",
        "south central": "SCENT",
        "west": "WEST",
    }

    check = []
    for i in range(len(COUNTY_REGIONS)):
        county = COUNTY_REGIONS.iloc[i]["county"]
        cdr_zone = COUNTY_REGIONS.iloc[i]["cdr_zone"]
        population = COUNTY_REGIONS.iloc[i]["population_2018"]
        cdr_zone = cdr_zone_dict[cdr_zone]
        if cdr_zone == "none":
            COUNTY_PERCENTAGE_OF_LOAD = 0
            COUNTY_LOADS[county] = 0
        else:
            COUNTY_PERCENTAGE_OF_LOAD = population / ERCOT_pop
            COUNTY_LOADS[county] = ERCOT_DATA["ERCOT"] * float(
                COUNTY_PERCENTAGE_OF_LOAD
            )
        check.append(COUNTY_PERCENTAGE_OF_LOAD)

    # Aggregate load per county into load per model region
    REGION_LOADS = date_time.copy()

    for i in range(len(LOAD_ZONES)):
        zone = LOAD_ZONES[i]
        sum_of_loads = []
        for j in range(len(COUNTY_REGIONS)):
            county = COUNTY_REGIONS.iloc[j]["county"]
            if COUNTY_REGIONS.iloc[j]["model_region"] == zone:
                if len(sum_of_loads) == 0:
                    sum_of_loads = COUNTY_LOADS[county]
                else:
                    sum_of_loads = [
                        x + y for x, y in zip(sum_of_loads, COUNTY_LOADS[county])
                    ]
        REGION_LOADS[zone] = sum_of_loads

    return REGION_LOADS


def EV_load_by_model_region(LOAD_ZONES, EV_DATA, COUNTY_REGIONS):
    # Finding the total population of ERCOT
    NON_LOAD = COUNTY_REGIONS[COUNTY_REGIONS.cdr_zone.isin(["non-load", "none"])]
    ERCOT_pop = sum(COUNTY_REGIONS["population_2018"]) - sum(
        NON_LOAD["population_2018"]
    )

    # Find load per county
    cdr_zone_dict = {
        "non-load": "none",
        "none": "none",
        "coast": "COAST",
        "east": "EAST",
        "far west": "FWEST",
        "north": "NORTH",
        "north central": "NCENT",
        "south": "SOUTH",
        "south central": "SCENT",
        "west": "WEST",
    }
    COUNTY_LOADS = pd.DataFrame()
    check = []
    for i in range(len(COUNTY_REGIONS)):
        county = COUNTY_REGIONS.iloc[i]["county"]
        cdr_zone = COUNTY_REGIONS.iloc[i]["cdr_zone"]
        population = COUNTY_REGIONS.iloc[i]["population_2018"]
        cdr_zone = cdr_zone_dict[cdr_zone]
        if cdr_zone == "none":
            COUNTY_PERCENTAGE_OF_LOAD = 0
            COUNTY_LOADS[county] = 0
        else:
            COUNTY_PERCENTAGE_OF_LOAD = population / ERCOT_pop
            COUNTY_LOADS[county] = EV_DATA * float(COUNTY_PERCENTAGE_OF_LOAD)
        check.append(COUNTY_PERCENTAGE_OF_LOAD)
    COUNTY_LOADS.fillna(0, inplace=True)

    # Aggregate load per county into load per model region
    REGION_LOADS = pd.DataFrame()
    for i in range(len(LOAD_ZONES)):
        zone = LOAD_ZONES[i]
        sum_of_loads = []
        for j in range(len(COUNTY_REGIONS)):
            county = COUNTY_REGIONS.iloc[j]["county"]
            if COUNTY_REGIONS.iloc[j]["model_region"] == zone:
                if len(sum_of_loads) == 0:
                    sum_of_loads = COUNTY_LOADS[county]
                else:
                    sum_of_loads = [
                        x + y for x, y in zip(sum_of_loads, COUNTY_LOADS[county])
                    ]
        REGION_LOADS[zone] = sum_of_loads

    return REGION_LOADS


# Import data
year = 2021
model_year = 2035

LOAD_ZONES = pd.read_csv("LOAD_ZONES.csv")["LOAD_ZONE"]

if year == 2021:
    ERCOT_DATA = pd.read_excel("data/Native_Load_%s_NOShed.xlsx" % str(year))
else:
    ERCOT_DATA = pd.read_excel("data/Native_Load_%s.xlsx" % str(year))
COUNTY_REGIONS = pd.read_excel("county_regions.xlsx")

# Formatting to GenX style
REGION_LOADS = load_by_model_region(LOAD_ZONES, ERCOT_DATA, COUNTY_REGIONS)

if len(REGION_LOADS) > 8760:
    REGION_LOADS = REGION_LOADS.drop(REGION_LOADS.index[1416:1440])
    REGION_LOADS.reset_index(inplace=True)

# Scaling
def load_scaling(LOADS, model_year):
    num_years = model_year - year
    LOADS_2 = LOADS.drop(["Year", "Month", "Day", "Period"], axis=1)
    LOADS_SCALED = LOADS_2 * (1.018**num_years)
    # LOADS_SCALED = LOADS_2 * (1.10**num_years)
    return LOADS_SCALED


def load_scaling_w_EV(LOADS, model_year):
    num_years = model_year - year
    LOADS_2 = LOADS.drop(["Year", "Month", "Day", "Period"], axis=1)
    LOADS_SCALED = LOADS_2 * (1.018**num_years)
    # LOADS_SCALED.drop('index',axis=1,inplace=True)

    ALL_EV_LOAD = pd.read_csv("data/ev_extra_loads.csv")
    # for i in range(num_years):
    #     EV_load_i = ALL_EV_LOAD[str(year+i+1)]
    #     EV_LOADS = pd.concat([EV_load_i]*365,ignore_index=True)
    #     EV_LOADS_BY_REGION = EV_load_by_model_region(LOAD_ZONES,EV_LOADS,COUNTY_REGIONS)

    #     LOADS_SCALED = LOADS_SCALED + EV_LOADS_BY_REGION

    EV_load_i = ALL_EV_LOAD[str(model_year)]
    EV_LOADS = pd.concat([EV_load_i] * 365, ignore_index=True)
    EV_LOADS_BY_REGION = EV_load_by_model_region(LOAD_ZONES, EV_LOADS, COUNTY_REGIONS)

    LOADS_SCALED = LOADS_SCALED + EV_LOADS_BY_REGION
    return LOADS_SCALED


# Load_data_profiles = load_scaling(REGION_LOADS,model_year)
Load_data_profiles = load_scaling_w_EV(REGION_LOADS, model_year)

# Write to .csv
Load_data_profiles.to_csv(
    "outputs/Load_profiles_%s_to_%s_EV.csv" % (str(year), str(model_year))
)
