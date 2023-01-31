"""
 This is a script to format raw ERCOT load profiles into the format desired for GenX modeling
 Options are described at bottom of script
"""

from pathlib import Path
from warnings import simplefilter

import pandas as pd

simplefilter(action="ignore", category=pd.errors.PerformanceWarning)

pd.options.mode.chained_assignment = None


def load_by_16_region(load, county_population_data):
    """Separates ERCOT cdr load profiles into 16 regions,
    requires preprocessing with county_population_data to include cdr_zone_percent"""
    # more of a code block/abstraction than a true function

    # create a profile for each county based on percentage of population in cdr_zone
    # by multiplying profile by that percentage
    county_loads = county_population_data.apply(
        lambda x: load[x["cdr_zone"]] * x["cdr_zone_percent"], axis=1
    ).T

    # aggregate county profiles into model region profiles
    # model_region_loads = load[
    #     ["Year", "Month", "Day", "Period"]
    # ]  # initialize with time columns
    model_region_loads = pd.DataFrame()
    for model_region in set(county_population_data["model_region"]):
        model_region_loads[model_region] = county_loads[
            county_population_data.index[
                county_population_data["model_region"] == model_region
            ].tolist()
        ].sum(
            axis=1
        )  # summing loads for each county in model region

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

    Example:
        df =
            value_column group_by_column
            1               a
            2               a
            3               a
            4               b
            5               b
            6               b

        returns:
            1/(1+2+3) # first value fraction of all of a
            2/6
            3/6
            4/(4+5+6) # first value fraction of all of b
            5/15
            6/15
    """

    return df[value_column] / df.groupby(group_by_column)[value_column].transform("sum")


def percentage_of_whole(df, value_column, group_by_column):
    """Creates dictionary where keys are values in group_by_column and values are
    percentage of total of value column

    Args:
        df (pandas.DataFrame): Contains data to be used
        value_column (string): column containing values to find percentage of whole
        group_by_column (string): column containing values to group by

    Returns:
        dict: keys are values in group_by_column and values are percentage of total of value column

    Example:
        df =
            value_column group_by_column
            1               a
            2               a
            3               a
            4               b
            5               b
            6               b

        returns:
            {'a': 6/21, 'b': 15/21}
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
    intermediate_year=None,
    intermediate_load=None,
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
        intermediate_year (numeric or str): Year of intermediate profile, only used for file naming purposes
                                            if none, does not scale to intermediate profile
                                            also does not scale if base year >= intermediate year
        intermediate_load (pandas.DataFrame): Load profile for scaling to intermediate year, scales on total energy

    Returns:
        dict: keys are years, values are load profiles for each model region
    """
    # make output folder
    output_dir_year = output_dir / f"load_base_{base_year}"

    if intermediate_year:
        # change dir if intermediate year
        output_dir_year = output_dir_year / f"load_intermediate_{intermediate_year}"

        # calculate sum
        intermediate_load_no_tz = intermediate_load.drop(columns=["Hour Ending"])
        intermediate_sum = intermediate_load_no_tz.sum().sum()

    output_dir_year.mkdir(parents=True, exist_ok=True)

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

    # sort 16region names, not great but best we can do since not alphanumeric
    names_16_region.sort()
    names_16_region = names_16_region[7:16] + names_16_region[0:7]

    out = {}
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
        assert tol > abs(
            total_16_region - total_base_profile
        ), "difference in total load greater than tolerance after splitting by 16 regions"

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

        if intermediate_year and (int(base_year) < int(intermediate_year)):
            # scale up to intermediate year by total energy
            # scale factor = total energy in intermediate year / total energy in base year
            load_profile_16_region *= intermediate_sum / total_16_region
            # years for load scaling
            n_years = model_year - int(intermediate_year)

        else:
            # years for load scaling
            n_years = model_year - int(base_year)

        # scale up to current model year from intermediate or base year
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

        # sort profiles before saving
        load_profile_16_region_scaled = load_profile_16_region_scaled[names_16_region]

        # save to dict
        out[
            output_dir_year / f"load_base{base_year}_model{model_year}.csv",
        ] = load_profile_16_region_scaled

    return out


def read_ercot_load_profile(path: Path) -> pd.DataFrame:
    """Returns dataframe, making column names consistent across years

    Args:
        path (Path): path to excel file

    Returns:
        pd.DataFrame: contains load profiles by region, with proper column names
    """

    df = pd.read_excel(path, index_col=0, parse_dates=True)
    df.index.name = "Hour Ending"
    df.reset_index(inplace=True)

    # since >>>errors="ignore"<<<, this will not raise an error
    # if the column names are already correct
    rename_columns = {
        "FAR_WEST": "FWEST",
        "NORTH_C": "NCENT",
        "SOUTHERN": "SOUTH",
        "SOUTH_C": "SCENT",
    }
    df.rename(
        columns=rename_columns,
        inplace=True,
        errors="ignore",
    )

    # drop ERCOT column
    df.drop(columns=["ERCOT"], inplace=True)

    # make sure all columns are correct
    true_columns = {
        "NORTH",
        "SOUTH",
        "COAST",
        "SCENT",
        "WEST",
        "NCENT",
        "FWEST",
        "Hour Ending",
        "EAST",
    }
    assert set(df.columns) == true_columns, "Column names are not correct"

    return df


def main(
    output_dir,
    data_dir,
    load_files,
    intermediate_load=None,
    intermediate_year=None,
):

    county_populations = pd.read_csv(data_dir / "county_population_data.csv")
    ev_loads = pd.read_csv(data_dir / "ev_extra_loads.csv")

    # mapping of names in county population data to names used in load profiles
    # and drop counties that don't have an ERCOT load profile
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

    for base_year, file_name in load_files.items():

        base_profile = read_ercot_load_profile(file_name)

        files = generate_16_region_load_profiles(
            base_profile,
            base_year=base_year,
            output_dir=output_dir,
            model_years=[2030, 2035],
            county_population_data=county_populations,
            ev_loads=ev_loads,
            intermediate_load=intermediate_load,
            intermediate_year=intermediate_year,
        )

        for file, df in files.items():
            df.to_csv(file[0])


if __name__ == "__main__":
    ###### OPTIONS ######

    input_dir = Path("inputs")  # location of input files
    output_dir = Path("outputs")  # location of output files
    data_dir = Path(
        "data"
    )  # location of data, looks for "county_population_data.csv" and "ev_extra_loads.csv"

    load_files = {
        "2002": input_dir / "2002_ercot_hourly_load_data.xls",
        "2003": input_dir / "2003_ercot_hourly_load_data.xls",
        "2014": input_dir / "2014_ercot_hourly_load_data.xls",
        "2020": input_dir / "Native_Load_2020.xlsx",
        "2021": input_dir / "Native_Load_2021_NOShed.xlsx",
    }

    intermediate_load = read_ercot_load_profile(input_dir / "Native_Load_2020.xlsx")
    intermediate_year = 2020

    ###### END OPTIONS ######
    main(
        output_dir=output_dir,
        data_dir=data_dir,
        load_files=load_files,
        intermediate_load=intermediate_load,
        intermediate_year=intermediate_year,
    )
