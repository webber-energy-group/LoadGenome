# LoadGenome

LoadGenome is a tool for compiling ERCOT load data into WEG's 16 regions.

This tool splits ERCOT load profiles (given by 8 "CDR zone" regions) into 16 regions to be used by other models.
This is achieved by splitting each CDR zone's profile into a profile for each member county, with weighting assigned by the county's percentage of the CDR zone's population.
These county level profiles are aggregated (summed) by assigned region from our 16 regions.

If a load profile is from a leap year, hours 1416 through 1440 (Feb 29) are dropped from the profile.

Furthermore, this tool can be used to optionally scale load to an "intermediate year" and scale annually by a fixed percent.
When scaling to an intermediate year, the tool scales the input load such that the sum of load is the same as the intermediate load. If a input/base profile has a total energy of 10 TWh and the intermediate profile has a total energy of 100 TWh, all load values in the base profile would be multiplied by 10.
Scaling annually is performed as
$$ \text{New Load} = \text{Load} \cdot s^{(n_f-n_0)}$$
where $\text{Load}$ is a load value, $s$ is a scaling factor (typically 1.018), $n_f$ is the desired final/model year, and $n_0$ is the year of the profile (which would be the base year, or intermediate profile year if that is used).

EV load can also be added to load profiles. Since EV data tend to not vary daily, a 24 hour profile is given for a year. The model repeats the 24 hour profile 365 times and adds it to the final profile after scaling.

## Usage

Configure `load_profile.py` and execute.

Under the `if __name__ == "__main__"` conditional, there are several options that can be configured:

| Variable | Type | Description |
| -----    | ---  | ---         |
| `input_dir` | Path-like | location of input (load) files. |
| `output_dir` | Path-like | location of output (scaled load) files. |
| `data_dir` | Path-like | location of other data, specifically `county_population_data.csv` and `ev_extra_loads.csv`. |
| `load_files` | Dictionary | Keys represent years of load files to be scaled while values are the locations of said load files (usually relative to `input_dir`). |
| `model_years` | List of integers | Years to which load will be scaled to. |
| `intermediate_load` | String/DataFrame/None | Intermediate load profile, optional.|
| `intermediate_year` | Integer/None | Year of intermediate load profile, optional.|

### Files

| File | Description |
| ---  | ---         |
| Input load profile | First column is a time index, with subsequent columns being load per region. Current data are unedited, backcasted (Actual) load profiles obtained from [ERCOT](https://www.ercot.com/mktinfo/loadprofile/alp).|
| `county_population_data.csv` | Contains county population data by county and year. Also assigns counties to both regions from the original load profiles (CDR zones) and desired regions (16 regions). Data can be found on [census.gov](https://www.census.gov/programs-surveys/popest/data/tables.html).|
|`ev_extra_loads.csv` | 24 hour EV data by year. Turned into 8760 hour profiles by repeating 365 times. These profiles are added after all scaling.|
|Intermediate load profile | **OPTIONAL** Same format as input load profile. Scales inputted load profile to this profile's total energy (sum of all values).|

## Notebooks

WIP

## Acknowledgements

Originally designed by Thomas Deetjen, PhD

Initial code by Drew Kassel

Edited and refactored by Braden Pecora

Yearly county population compiled by Matthew Skiles
