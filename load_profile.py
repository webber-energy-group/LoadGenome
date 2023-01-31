"""
 This is a script to format raw ERCOT load profiles into the format desired for GenX modeling
"""

from pathlib import Path
from warnings import simplefilter

import pandas as pd

simplefilter(action="ignore", category=pd.errors.PerformanceWarning)

pd.options.mode.chained_assignment = None


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
    """Gets timeseries of ERCOT load profile

    Args:
        base_profile (pandas.DataFrame): load profile

    Returns:
        pandas.DataFrame: DataFrame with separate columns for Year, Month, Day, and Period
    """
    date_time = pd.DataFrame()

    times = base_profile["Hour Ending"]
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


def load_by_16_region(load, county_population_data):

    # create a profile for each county based on percentage of population in cdr_zone
    # by multiplying profile by that percentage
    county_loads = county_population_data.apply(
        lambda x: load[x["cdr_zone"]] * x["cdr_zone_percent"], axis=1
    ).T

    # aggregate county profiles into model region profiles
    model_region_loads = load[["Year", "Month", "Day", "Period"]]
    for model_region in set(county_population_data["model_region"]):
        model_region_loads[model_region] = county_loads[
            county_population_data.index[
                county_population_data["model_region"] == model_region
            ].tolist()
        ].sum(axis=1)

    return model_region_loads


def percentage_of_whole_for_each(df, value_column, group_by_column):
    """returns a pandas series of the fractional value of each value in
    'value_column' where the whole is the the sum of all values (in value column)
    that match the same group_by_column value

    Args:
        df (pandas.DataFrame): Contains data to be used
        value_column (string): column containing values to find percentage of whole
        group_by_column (string): column containing values to group by

    Returns:
        pandas.Series: index corresponds to value_column
    """

    return df[value_column] / df.groupby(group_by_column)[value_column].transform("sum")


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


def generate_16_region_load_profiles(
    base_profile,
    base_year,
    output_dir,
    model_years,
    county_population_data,
    ev_loads,
    scaling_factor=1.018,
):
    """Scales base profile to intermediate profile's energy, and then scales that 1.018 per year to each model year

    Args:
        base_profile (pandas.DataFrame): Load profile for base year
        base_year (numeric): Year of initial profile
        output_dir (pathlib.Path): directory for output files
        model_years (list): list of years the model needs load data for
        county_population_data (pandas.DataFrame): Contains population data for each county for each model year
        ev_loads (pandas.DataFrame): Contains EV load data for each county for each model year (24 hours)
        scaling_factor (float like): Factor to scale load by each year (from first model year)
    """
    # make output folder
    output_dir_year = output_dir / f"load_base_{base_year}"
    output_dir_year.mkdir(parents=True, exist_ok=True)

    # something to verify time
    date_time = ERCOT_hour_ending_to_datetime(base_profile)

    base_profile = date_time.merge(base_profile, left_index=True, right_index=True)
    base_profile.drop(["Hour Ending"], axis=1, inplace=True)

    ## process population data for given base year
    county_population_data = county_population_data[
        ["county", "cdr_zone", "model_region", base_year]
    ]
    county_population_data.rename(columns={base_year: "population"}, inplace=True)

    # get percent cdr, percent model_region
    county_population_data["cdr_zone_percent"] = percentage_of_whole_for_each(
        county_population_data, "population", "cdr_zone"
    )
    county_population_data.set_index("county", inplace=True)

    # get percent of population in each model region (for splitting EV load)
    population_fraction_16_region = percentage_of_whole(
        county_population_data, "population", "model_region"
    )

    ## get region names
    names_16_region = list(set(county_population_data["model_region"]))
    names_cdr_region = list(set(county_population_data["cdr_zone"]))

    # I hate this
    names_16_region.sort()
    names_16_region = names_16_region[7:16] + names_16_region[0:7]

    for model_year in model_years:

        # Switch cdr regions to model regions
        load_profile_16_region = load_by_16_region(
            load=base_profile,
            county_population_data=county_population_data,
        )

        # check error
        total_16_region = load_profile_16_region[names_16_region].sum().sum()
        total_base_profile = base_profile[names_cdr_region].sum().sum()

        tol = 1e-4
        assert tol > abs(total_16_region - total_base_profile)

        # drop leap year, if relevant
        if len(load_profile_16_region) > 8760:
            load_profile_16_region = load_profile_16_region.drop(
                load_profile_16_region.index[1416:1440]
            )
            load_profile_16_region.reset_index(inplace=True)

        # Not sure if this the Year, Month, Day, Period columns are needed,
        # but it doesn't hurt to keep as is
        load_profile_16_region.drop(
            ["index", "Year", "Month", "Day", "Period"],
            axis=1,
            inplace=True,
            errors="ignore",
        )

        # scale up to first model year
        # TODO
        #
        #

        # scale up to current model year
        n_years = model_year - int(base_year)
        load_profile_16_region_scaled = load_profile_16_region * (
            scaling_factor**n_years
        )

        # add EV load
        ev_load = ev_loads[str(model_year)]
        ev_load = pd.concat([ev_load] * 365, ignore_index=True)

        for model_region in load_profile_16_region_scaled.columns:
            load_profile_16_region_scaled[model_region] += (
                ev_load * population_fraction_16_region[model_region]
            )

        # sort profiles
        load_profile_16_region_scaled = load_profile_16_region_scaled[names_16_region]

        # save to file
        load_profile_16_region_scaled.to_csv(
            output_dir_year / f"load_base{base_year}_model{model_year}.csv",
        )


def main():

    ###### OPTIONS ######

    input_dir = Path("inputs")  # location of input files
    output_dir = Path("outputs")  # location of output files
    data_dir = Path("data")  # location of data (EV Load, county population, etc.)

    # load_files = [
    #     input_dir / "Native_Load_2020.xlsx",
    #     input_dir / "Native_Load_2021_NOShed.xlsx",
    # ] # list specific files with Path objects
    load_files = input_dir.glob(
        "*.xlsx"
    )  # list of Path objects to all .xlsx files in input_dir
    #####################

    county_populations = pd.read_csv(data_dir / "county_population_data.csv")
    ev_loads = pd.read_csv(data_dir / "ev_extra_loads.csv")

    cdr_zone_dict = {
        "non-load": None,
        "none": None,
        "coast": "COAST",
        "east": "EAST",
        "far west": "FWEST",
        "north": "NORTH",
        "north central": "NCENT",
        "south": "SOUTH",
        "south central": "SCENT",
        "west": "WEST",
    }

    county_populations["cdr_zone"] = county_populations["cdr_zone"].map(cdr_zone_dict)
    county_populations.dropna(inplace=True)

    for file_name in load_files:
        base_year = file_name.stem.split("_")[2]

        base_profile = pd.read_excel(file_name, index_col=0)
        base_profile.index.name = "Hour Ending"
        base_profile.reset_index(inplace=True)

        generate_16_region_load_profiles(
            base_profile,
            base_year=base_year,
            output_dir=output_dir,
            model_years=[2030, 2035],
            county_population_data=county_populations,
            ev_loads=ev_loads,
            # load_zones=load_zones, #set(df["model_region"]) and drop none
            # county_regions=county_regions,
        )


if __name__ == "__main__":
    main()
