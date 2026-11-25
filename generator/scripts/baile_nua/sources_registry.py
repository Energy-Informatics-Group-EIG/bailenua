"""The declared public sources for this build.

Nothing is downloaded that is not declared here.  Licences are recorded as the
publisher states them; where a publisher's terms could not be read from the
response, the licence field says so rather than guessing, and the E1 report
carries it as an open item.

Deliberately absent: CER/ISSDA, POWSCAR microdata, and any other licensed or
restricted source.  The brief forbids them and E1 depends on none of them.
"""

from __future__ import annotations

from baile_nua.sources import Source, register

CSO_BASE = "https://www.cso.ie/en/media/csoie/census/census2022"

# Licence strings, as published.
CSO_LICENCE = "CC-BY 4.0 (CSO Open Data; https://www.cso.ie/en/aboutus/termsandconditions/)"
OSI_LICENCE = "CC-BY 4.0 (Ordnance Survey Ireland / Tailte Éireann open data)"
EUROSTAT_LICENCE = "CC-BY 4.0 (Eurostat re-use policy)"
MET_LICENCE = "CC-BY 4.0 (Met Éireann open data)"
SEAI_LICENCE = "SEAI open data; terms to be confirmed in WP1 (U05)"
#: ESB Networks' Standard Load Profiles are published without registration
#: through the Retail Market Design Service for the Irish retail electricity
#: market. Public, and the re-use terms are not stated on the page, so this is
#: recorded as unconfirmed rather than assumed to be open (U05's treatment of
#: SEAI).
RMDS_LICENCE = (
    "ESB Networks / Retail Market Design Service published market data; "
    "re-use terms not stated on the publication page, to be confirmed in WP1"
)

# --------------------------------------------------------------------------- #
# CSO Census 2022 Small Area Population Statistics (design 5.2 step 1, R04)
# --------------------------------------------------------------------------- #

register(Source(
    key="cso.saps2022.small_area",
    url=f"{CSO_BASE}/SAPS_2022_Small_Area_UR_171024.csv",
    relpath="cso/SAPS_2022_Small_Area_UR_171024.csv",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="Census 2022 Small Area Population Statistics (all small areas, urban/rural)",
    intended_use="calibration",
    model_development_exposure="none",
    used_for=(
        "R04 / design 5.2 step 1: every SAPS marginal for Cobh's small areas - "
        "age by sex, household composition and size, nationality, ethnicity, "
        "language, education, principal economic status, socio-economic group, "
        "industry, occupation, tenure, dwelling type and year built, central "
        "heating fuel, car availability, travel to work. Also U03 scale-down."
    ),
))

register(Source(
    key="cso.saps2022.glossary",
    url=f"{CSO_BASE}/Glossary_Saps_2022_REVISED_21102024.xlsx",
    relpath="cso/Glossary_Saps_2022_REVISED_21102024.xlsx",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="Census 2022 SAPS glossary (column name to field description)",
    intended_use="reference",
    used_for=(
        "Decoding the 795 SAPS columns into the 48 themed tables. Required so "
        "that no marginal is assembled from a column guessed by its name."
    ),
))

register(Source(
    key="cso.saps2022.bua",
    url=f"{CSO_BASE}/SAPS_2022_BUA_270923.csv",
    relpath="cso/SAPS_2022_BUA_270923.csv",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="Census 2022 SAPS by Built-Up Area",
    intended_use="calibration",
    used_for=(
        "The Cobh town total against which the sum of the 53 small areas is "
        "reconciled, and the denominator for the U03 scale-down factor."
    ),
    encoding="cp1252",
))

register(Source(
    key="cso.saps2022.ed",
    url=f"{CSO_BASE}/SAPS_2022_CSOED3270923.csv",
    relpath="cso/SAPS_2022_CSOED3270923.csv",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="Census 2022 SAPS by CSO Electoral Division",
    intended_use="reference",
    used_for=(
        "Confirming that Cobh Urban and Cobh Rural are the two EDs covering the "
        "Cobh built-up area, as the OSi small-area attributes report."
    ),
    encoding="cp1252",
))

# --------------------------------------------------------------------------- #
# OSi / Tailte Éireann small-area boundaries (design 5.2 step 2 spatial metrics)
# --------------------------------------------------------------------------- #

_OSI_SA = (
    "https://services-eu1.arcgis.com/BuS9rtTsYEV5C0xh/arcgis/rest/services/"
    "Small_Area_National_Statistical_Boundaries_2022_Ungeneralised_view/FeatureServer/0/query"
)

register(Source(
    key="osi.small_areas_2022.cobh",
    url=(
        _OSI_SA
        + "?where=SA_URBAN_AREA_NAME%3D%27Cobh%27"
        + "&outFields=SA_GEOGID_2022,SA_PUB2022,SA_URBAN_AREA_NAME,SA_URBAN_AREA_FLAG,"
          "ED_ENGLISH,ED_ID_STR,COUNTY_ENGLISH,SA_NUTS3,SA_NUTS3_NAME,CSO_LEA,Shape__Area"
        + "&returnGeometry=true&outSR=4326&f=geojson"
    ),
    relpath="cso/osi_small_areas_2022_cobh.geojson",
    licence=OSI_LICENCE,
    publisher="Ordnance Survey Ireland / Tailte Éireann (via OSi Open Data)",
    title="CSO Small Areas, National Statistical Boundaries 2022, ungeneralised - Cobh built-up area",
    intended_use="calibration",
    used_for=(
        "The small-area-to-town correspondence (SA_URBAN_AREA_NAME = 'Cobh'), "
        "which the SAPS small-area file does not carry, plus the geometry needed "
        "for the U03 spatial comparison (design 5.2 step 2: spatial segregation "
        "indices) and for the real NUTS3 code used in the MIMIC crosswalk."
    ),
))

# --------------------------------------------------------------------------- #
# Eurostat HETUS time-use aggregates (E0-2 / U04, risk K02)
# --------------------------------------------------------------------------- #

_ESTAT = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data"

# NOTE on HETUS coverage, found by inspecting the retrieved data (ISSUES.md I-008):
#   * HETUS 2020 (`tus_20*`) covers 11 countries: AT BG DE EE FI HR HU NL NO PL RS.
#   * HETUS 2000/2010 (`tus_00*`) covers 22: AT BE BG DE EE EL ES FI FR HU IT LT
#     LU LV NL NO PL RO RS SI TR UK.
#   Ireland appears in NEITHER. U04 assumed HETUS could be given "Irish
#   recalibration"; there is no Irish row in HETUS to recalibrate against.
#   So the 2000/2010 wave is used with geo='UK' as the structural donor - the
#   design itself names "HETUS/UK TUS" - and the Irish anchoring comes from
#   Cobh's own Census 2022 travel-to-work, time-leaving-home, journey-time and
#   working-from-home tables, which are real Irish data for this town. The
#   activity engine stays flagged VERIFIED, NOT CALIBRATED (E0-2).

register(Source(
    key="eurostat.hetus.tus_00age",
    url=f"{_ESTAT}/tus_00age/?format=SDMX-CSV&compressed=false",
    relpath="eurostat/tus_00age.csv",
    licence=EUROSTAT_LICENCE,
    publisher="Eurostat",
    title="HETUS 2000/2010: time spent, participation time and participation rate in the main activity by sex and age group (tus_00age)",
    intended_use="calibration",
    substitute_flag="[A] UK donor; HETUS has no Irish data at all (I-008, U04, K02)",
    used_for=(
        "Age- and sex-conditioned activity durations, the base layer of the "
        "semi-Markov duration distributions (design 5.3)."
    ),
))

register(Source(
    key="eurostat.hetus.tus_00week",
    url=f"{_ESTAT}/tus_00week/?format=SDMX-CSV&compressed=false",
    relpath="eurostat/tus_00week.csv",
    licence=EUROSTAT_LICENCE,
    publisher="Eurostat",
    title="HETUS 2000/2010: time spent in the main activity by sex and day of the week (tus_00week)",
    intended_use="calibration",
    substitute_flag="[A] UK donor; HETUS has no Irish data at all (I-008, U04, K02)",
    used_for=(
        "The weekday/weekend split of activity durations (design 5.3: durations "
        "conditioned on day type)."
    ),
))

register(Source(
    key="eurostat.hetus.tus_00selfstat",
    url=f"{_ESTAT}/tus_00selfstat/?format=SDMX-CSV&compressed=false",
    relpath="eurostat/tus_00selfstat.csv",
    licence=EUROSTAT_LICENCE,
    publisher="Eurostat",
    title="HETUS 2000/2010: time spent in the main activity by sex and self-declared labour status (tus_00selfstat)",
    intended_use="calibration",
    substitute_flag="[A] UK donor; HETUS has no Irish data at all (I-008, U04, K02)",
    used_for=(
        "Employment-conditioned activity shares (design 5.3 'conditioned on "
        "person type'), which is what separates a working adult's weekday from a "
        "retired person's."
    ),
))

register(Source(
    key="eurostat.hetus.tus_00hhstatus",
    url=f"{_ESTAT}/tus_00hhstatus/?format=SDMX-CSV&compressed=false",
    relpath="eurostat/tus_00hhstatus.csv",
    licence=EUROSTAT_LICENCE,
    publisher="Eurostat",
    title="HETUS 2000/2010: time spent in the main activity by sex and household composition (tus_00hhstatus)",
    intended_use="calibration",
    substitute_flag="[A] UK donor; HETUS has no Irish data at all (I-008, U04, K02)",
    used_for=(
        "Household-composition-conditioned shares, the only public evidence "
        "available for the household coupling in design 5.3 (risk K08: little "
        "quantitative evidence exists for negotiation and influence)."
    ),
))

register(Source(
    key="eurostat.hetus.tus_00startime",
    url=f"{_ESTAT}/tus_00startime/?format=SDMX-CSV&compressed=false",
    relpath="eurostat/tus_00startime.csv",
    licence=EUROSTAT_LICENCE,
    publisher="Eurostat",
    title="HETUS 2000/2010: participation rate in the main activity by sex and time of the day (tus_00startime)",
    intended_use="calibration",
    # TUNING-EXPOSED for activity timing (I-060). U32 derived the bedtime and
    # wake-time quantile offsets from this table's AC0A curve, and week 3 step
    # 2 derives appliance-triggering activity timing from the same table. So
    # the "awake-share fit" and the V0 activity-share check are CONSISTENCY
    # checks against a calibration input - they test that the implementation
    # reproduces the curve it was given, which is a real and useful thing to
    # test and is not evidence that Irish timing resembles the model's.
    #
    # The independent validation of the resulting LOAD shape is ESB Networks
    # LP1 through PL-PEAK-01, at exposure "none". LP1 must never be tuned
    # against, or that independence goes too.
    model_development_exposure="tuning",
    substitute_flag="[A] UK donor; HETUS has no Irish data at all (I-008, U04, K02)",
    used_for=(
        "The diurnal participation profile. This is the single most important "
        "HETUS table for a semi-Markov engine, because it constrains WHEN each "
        "activity happens rather than only how long it lasts. TUNING-EXPOSED "
        "for activity timing: U32's sleep offsets and week 3's appliance "
        "timing are derived from it, so the awake-share fit and the V0 "
        "activity-share check are CONSISTENCY checks against a calibration "
        "input and NOT independent validations. The independent check on the "
        "resulting load shape is LP1 via PL-PEAK-01, exposure 'none'. "
        "See I-060."
    ),
))

# --------------------------------------------------------------------------- #
# CSO vital statistics (design 5.9 life-course hazards, R08)
# --------------------------------------------------------------------------- #

_PXSTAT = "https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset"
_PXSTAT_COLLECTION = (
    "https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadCollection"
)

# U30 (9 Oct 2026). The whole PxStat catalogue, as one JSON-stat collection:
# every table the CSO publishes, with its matrix code, title and the LABEL OF
# EVERY DIMENSION. The dimension labels are the point - "Appliance", "Type of
# Private Accommodation", "Age of Mother" - because a table whose title does
# not say what it breaks down by is invisible to a title-only search, and
# HAS02 (I-040) was found exactly that way.
#
# This is declared as a source rather than queried live so that the U30 sweep
# is reproducible: the verdict "nothing public exists for this" is only as
# good as the catalogue it was taken over, and that catalogue has a date and a
# hash like any other input. exposure="design" is the honest tag: what the
# sweep finds decides which assumptions stay assumptions.
register(Source(
    key="cso.pxstat.collection",
    url=_PXSTAT_COLLECTION,
    relpath="cso/pxstat_collection.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="PxStat full table catalogue (ReadCollection): all CSO tables with titles and dimension labels",
    intended_use="reference",
    model_development_exposure="design",
    used_for=(
        "U30: the sweep of every remaining [A] assumption flag against what "
        "the CSO actually publishes. Each flag is either retired against a "
        "named table or kept with the search that failed to find one "
        "(docs/ISSUES.md I-040: an [A] flag should record what was searched)."
    ),
))


register(Source(
    key="cso.vitalstats.vsa104_fertility_rates_by_age",
    url=f"{_PXSTAT}/VSA104/JSON-stat/2.0/en",
    relpath="cso_vitalstats/VSA104_fertility_rates_by_age_group_and_region.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="VSA104: fertility rates by age group and NUTS 3 region",
    intended_use="calibration",
    model_development_exposure="none",
    used_for=(
        "WP5 / week 2 step 5: the age-specific fertility hazard (design 5.9 "
        "birth row, R08). Published as a RATE by age group and region, so the "
        "South-West figure needs no denominator from another table."
    ),
))

register(Source(
    key="cso.vitalstats.vsa36_births_by_age_and_parity",
    url=f"{_PXSTAT}/VSA36/JSON-stat/2.0/en",
    relpath="cso_vitalstats/VSA36_births_by_age_of_mother_and_parity.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="VSA36: births by year, age of mother at maternity and previous liveborn children",
    intended_use="calibration",
    model_development_exposure="none",
    used_for=(
        "WP5 birth hazard, parity dimension: design 5.9 asks for age- AND "
        "parity-specific fertility, and VSA104 carries age only. These are "
        "counts, so they give the parity SHARE within an age group, which "
        "then splits the VSA104 rate."
    ),
))

register(Source(
    key="cso.vitalstats.vsa08_deaths_by_age_and_sex",
    url=f"{_PXSTAT}/VSA08/JSON-stat/2.0/en",
    relpath="cso_vitalstats/VSA08_deaths_occurring_by_age_group_and_sex.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="VSA08: deaths occurring by year, sex, cause of death and age group at death",
    intended_use="calibration",
    model_development_exposure="none",
    used_for=(
        "WP5 mortality hazard, numerator: deaths by age group and sex for a "
        "recent year (all causes). CEPHA05, the decennial life table, is the "
        "only table PxStat publishes as a life table and it stops at 1990, "
        "which cannot age a 2022 population."
    ),
))

register(Source(
    key="cso.population.pea01_population_estimates_by_age_sex",
    url=f"{_PXSTAT}/PEA01/JSON-stat/2.0/en",
    relpath="cso_vitalstats/PEA01_population_estimates_by_age_group_and_sex.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="PEA01: population estimates (persons in April) by year, age group and sex",
    intended_use="calibration",
    model_development_exposure="none",
    used_for=(
        "WP5 mortality hazard, denominator. Paired with VSA08 on the same "
        "year and the same age groups this makes the age- and sex-specific "
        "death rate a RATIO OF TWO PUBLISHED NUMBERS, with no population "
        "estimate of our own in it."
    ),
))

# --------------------------------------------------------------------------- #
# CSO Building Energy Rating data (design 5.2 step 1, 5.7, S03; closes I-011)
# --------------------------------------------------------------------------- #

register(Source(
    key="cso.ber.eba02_by_county",
    # CSV is refused with a bare 403: the real reason, visible only through the
    # JSON-RPC endpoint, is "You are attempting to download 6800112 data cells
    # in CSV. This exceeds the maximum of 1048575". JSON-stat has no such cap.
    url=f"{_PXSTAT}/EBA02/JSON-stat/2.0/en",
    relpath="seai/EBA02_domestic_ber_by_county.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland), from the SEAI BER register",
    title="Domestic Building Energy Rating by BER band, dwelling type, heating fuel, year of construction and county (EBA02)",
    intended_use="calibration",
    used_for=(
        "Closes I-011. SAPS Table 6.1 publishes only House/Bungalow vs "
        "Flat/Apartment, but the schema's dwelling_type enum, the archetype "
        "library (5.7) and U18's 'Terraced' gap all need houses split into "
        "detached, semi-detached and terraced. EBA02 gives that split for "
        "Co. Cork, crossed with BER band and year of construction, so D02's BER "
        "and fabric parameters are conditioned on real Irish data rather than on "
        "an assumption. The house/apartment RATIO stays anchored to the Census "
        "marginal; BER supplies only the within-house split."
    ),
))

register(Source(
    key="cso.ber.ebq02_renewables",
    url=f"{_PXSTAT}/EBQ02/JSON-stat/2.0/en",
    relpath="seai/EBQ02_domestic_ber_renewables_by_region.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland), from the SEAI BER register",
    title="Domestic Building Energy Ratings by dwelling type, renewable energy source, year of construction, heating fuel and NUTS3 region (EBQ02)",
    intended_use="calibration",
    used_for=(
        "Also closes I-011. Census records heating FUEL, so a heat pump and "
        "direct electric resistance heating are the same row ('Electricity') - "
        "yet their COP differs by a factor of three or more and dominates the "
        "heating load (design 5.7). EBQ02 reports heat-pump and solar-panel "
        "penetration for the South-West NUTS3 region, which is Cork (IE053, "
        "confirmed from the OSi small-area attributes), so the split within "
        "electrically-heated homes comes from real regional data. Also supplies "
        "the PV and heat-pump adoption base rates for D04 at t0 (5.9 DER row)."
    ),
))

# --------------------------------------------------------------------------- #
# CSO baby names (design 5.2 step 6, R26, R27, K12)
# --------------------------------------------------------------------------- #

register(Source(
    key="cso.babynames.boys",
    url=f"{_PXSTAT}/VSA50/CSV/1.0/en",
    relpath="cso/VSA50_boys_names.csv",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="Boys' names in Ireland with 3 or more occurrences, by year (VSA50)",
    intended_use="calibration",
    used_for=(
        "D05.given_name for males. Design 5.2 step 6: 'Draw first names by birth "
        "year and origin from CSO baby-name tables'. Covers registration years "
        "1964 to 2025, so a person born in those years gets a name drawn from the "
        "frequencies that actually applied in their birth year."
    ),
))

register(Source(
    key="cso.babynames.girls",
    url=f"{_PXSTAT}/VSA60/CSV/1.0/en",
    relpath="cso/VSA60_girls_names.csv",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="Girls' names in Ireland with 3 or more occurrences, by year (VSA60)",
    intended_use="calibration",
    used_for="D05.given_name for females; as VSA50.",
))

# --------------------------------------------------------------------------- #
# Met Éireann historical data (design 5.1 / S01, D15 and D31)
# --------------------------------------------------------------------------- #

register(Source(
    key="met.roches_point.hourly",
    # Station 1075. The first attempt used 1575, which turned out to be MALIN
    # HEAD in Co. Donegal - the opposite end of the island - and was caught only
    # because the CSV carries its own station name in the header (I-017). The
    # identity of every station file is now asserted on read.
    url="https://clidata.met.ie/cli/climate_data/webdata/hly1075.zip",
    relpath="met_eireann/hly1075_roches_point.zip",
    licence=MET_LICENCE,
    publisher="Met Éireann",
    title="Hourly climate data, Roches Point (station 1075, 51.793N 8.244W, 40 m)",
    substitute_flag=None,
    intended_use="calibration",
    used_for=(
        "The 2022 weather realisation. Roches Point is the coastal station at the "
        "mouth of Cork Harbour, closest to Cobh's exposure, so it drives the true "
        "site series D15 after downscaling."
    ),
))

register(Source(
    key="met.cork_airport.hourly",
    url="https://clidata.met.ie/cli/climate_data/webdata/hly3904.zip",
    relpath="met_eireann/hly3904_cork_airport.zip",
    licence=MET_LICENCE,
    publisher="Met Éireann",
    title="Hourly climate data, Cork Airport (station 3904)",
    intended_use="calibration",
    used_for=(
        "The observable station series D31. Design 6.4 item 7 requires the "
        "observable weather to come from the nearest official station rather than "
        "the true site microclimate; Cork Airport is inland and elevated, so the "
        "station-to-site gap is physically real rather than injected noise."
    ),
))

# --------------------------------------------------------------------------- #
# CSO household electricity consumption (closes I-027: the device layer had no
# public Irish target, and the first E1 estate drew 16.4 kWh/day of appliance
# electricity alone - about 40% above the national mean for ALL household
# electricity including heating.)
# --------------------------------------------------------------------------- #

register(Source(
    key="cso.electricity.dbere101_by_dwelling_ber",
    url=f"{_PXSTAT}/DBEREL01/JSON-stat/2.0/en",
    relpath="cso_electricity/DBEREL01_household_electricity_by_dwelling_and_ber.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland), from matched BER and ESB Networks meter data",
    title="Household Electricity Consumption by type of dwelling, energy rating and year (DBEREL01)",
    intended_use="calibration",
    model_development_exposure="tuning",
    used_for=(
        "D24 calibration target for the device and DER layer (design 5.6, 7.2). "
        "The dimensions are exactly the archetype library's own - dwelling type "
        "crossed with BER band - so the target applies per dwelling rather than "
        "only to the town mean, which is what distinguishes 'the average home "
        "uses about the right amount' from 'each KIND of home does'. 2022 is "
        "t0, so the comparison year is the simulated year. Exposure is declared "
        "as 'tuning' because the appliance trigger rates WERE adjusted against "
        "it: 7.1 requires that to be visible, not buried. So PL-ELEC-01, which "
        "scores against this table, is a CONSISTENCY check against a "
        "calibration input and NOT an independent validation - the "
        "held-out electricity axis is DBEREL02 (dwelling type x period of "
        "construction), exposure 'none'. See I-058."
    ),
))

register(Source(
    key="cso.electricity.dbere102_by_dwelling_construction",
    url=f"{_PXSTAT}/DBEREL02/JSON-stat/2.0/en",
    relpath="cso_electricity/DBEREL02_household_electricity_by_dwelling_and_construction.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland), from matched BER and ESB Networks meter data",
    title="Household Electricity Consumption by type of dwelling, period of construction and year (DBEREL02)",
    intended_use="calibration",
    model_development_exposure="none",
    used_for=(
        "The held-out half of the device-layer check. DBEREL01 (dwelling x BER) "
        "is what the trigger rates were tuned against, so it cannot also measure "
        "whether they generalise. DBEREL02 crosses dwelling type with PERIOD OF "
        "CONSTRUCTION instead, a dimension the tuning never saw, and D02 already "
        "carries year_built_band, so it scores the same homes on an axis that was "
        "not fitted. Exposure stays 'none' and must stay 'none'."
    ),
))

register(Source(
    key="cso.electricity.mec05_by_tariff_group",
    url=f"{_PXSTAT}/MEC05/JSON-stat/2.0/en",
    relpath="cso_electricity/MEC05_metered_electricity_by_tariff_group.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland), from ESB Networks",
    title="Metered Electricity Consumption by tariff group and year (MEC05)",
    intended_use="reference",
    model_development_exposure="none",
    used_for=(
        "The aggregate cross-check, and the one that matches Cobh's own tariff "
        "group: 'Urban Residential' rather than a national all-dwellings mean. "
        "Cobh is a town, and urban residential consumption differs from rural "
        "(no oil-fired rural pattern, smaller dwellings). Reference and not "
        "calibration, because it cannot be made per-dwelling: the CSO publishes "
        "no meter COUNT by tariff group, so the 5,668 GWh has no denominator. "
        "It fixes the urban-to-rural RATIO (5,668 to 3,095 GWh) and nothing more."
    ),
))

register(Source(
    key="cso.electricity.mec03_by_county_sector",
    url=f"{_PXSTAT}/MEC03/JSON-stat/2.0/en",
    relpath="cso_electricity/MEC03_metered_electricity_by_county_and_sector.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland), from ESB Networks",
    title="Metered Electricity Consumption by county, sector and year (MEC03)",
    intended_use="reference",
    model_development_exposure="none",
    used_for=(
        "Co. Cork residential metered consumption, for the county-level sanity "
        "check. Reference rather than calibration: it is a county total, and "
        "Cobh's own small areas are a thin slice of it, so it can only show that "
        "the simulated estate is not wrong by a factor."
    ),
))

register(Source(
    key="cso.electricity.mec06_residential_meters",
    url=f"{_PXSTAT}/MEC06/JSON-stat/2.0/en",
    relpath="cso_electricity/MEC06_number_of_residential_electricity_meters.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland), from ESB Networks",
    title="Number of Residential Electricity Meters by county and year (MEC06)",
    intended_use="reference",
    model_development_exposure="none",
    used_for=(
        "The denominator for MEC03. A consumption total means nothing without "
        "the meter count that produced it, and deriving kWh per meter from two "
        "tables is the only way to get a per-dwelling figure for Co. Cork."
    ),
))

register(Source(
    key="cso.electricity.mec07_meters_by_county",
    url=f"{_PXSTAT}/MEC07/JSON-stat/2.0/en",
    relpath="cso_electricity/MEC07_residential_and_nonresidential_meters_by_county.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland), from ESB Networks",
    title="Residential and Non-Residential Electricity Meters by county and year (MEC07)",
    intended_use="calibration",
    model_development_exposure="none",
    used_for=(
        "The denominator that makes MEC03 usable, and the geographically "
        "matched aggregate target: MEC03's Co. Cork residential GWh divided by "
        "MEC07's Co. Cork residential meter count is mean annual kWh per "
        "residential meter in Cobh's own county for 2022. Design 6.4 keys the "
        "observable layer to the PREMISES (meter point), so a per-meter figure "
        "is the one that compares to what the model emits - a per-household "
        "figure would not, because a vacant dwelling still has a meter."
    ),
))

# --------------------------------------------------------------------------- #
# Eurostat ACL00 codelist (closes I-029: the activity-code mapping had no
# machine-readable labels behind it, and one mapping was wrong as a result.)
# --------------------------------------------------------------------------- #

register(Source(
    key="eurostat.codelist.acl00",
    url="https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/codelist/ESTAT/ACL00",
    relpath="eurostat/ACL00_activity_codelist.xml",
    licence=EUROSTAT_LICENCE,
    publisher="Eurostat",
    title="SDMX codelist ACL00: HETUS activity coding list, with English labels",
    intended_use="reference",
    model_development_exposure="none",
    used_for=(
        "The labels for the activity codes the HETUS tables are keyed by. The "
        "tus_00* downloads carry codes only - 'AC331', 'AC33A' - with no text, "
        "so until this was registered the mapping from an HETUS code to a "
        "modelled activity rested on recollection of what each code means. One "
        "of them was wrong: laundry was mapped to AC33A, which this codelist "
        "gives as 'Handicraft and producing textiles and other care for "
        "textiles' (2 minutes a day), when laundry is AC331 (5 minutes) and "
        "ironing AC332 (4). The brief forbids hard-coded statistics from "
        "memory; a code-to-meaning mapping from memory is the same failure one "
        "step removed, and this closes it."
    ),
))

# --------------------------------------------------------------------------- #
# CSO gas consumption and floor area (closes I-031: 49 of the 50 estate homes
# heat with gas, so the ELECTRICITY target could not see their heating at all,
# and the dwelling floor areas that drive it were wrong.)
# --------------------------------------------------------------------------- #

register(Source(
    key="cso.gas.dberng01_by_dwelling_ber",
    url=f"{_PXSTAT}/DBERNG01/JSON-stat/2.0/en",
    relpath="cso_electricity/DBERNG01_mean_gas_by_dwelling_and_ber.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland), from matched BER and Gas Networks Ireland meter data",
    title="Mean Gas Consumption by type of dwelling, energy rating and year (DBERNG01)",
    intended_use="calibration",
    model_development_exposure="tuning",
    used_for=(
        "The heating-side D24 target, and the one the estate actually needs: "
        "49 of its 50 homes heat with gas, so their space heat never appears in "
        "the electricity meter and DBEREL01 cannot see it. In a gas-heated "
        "dwelling, gas consumption IS space heating plus hot water, which makes "
        "this the direct check on the F1 physics and the heating schedule - the "
        "largest energy term in the model and, until now, the one with no "
        "public target at all. Same axes as DBEREL01 (dwelling type x BER "
        "band), so the two can be read together per dwelling. Exposure is "
        "'tuning' because the floor-area and room-allocation fixes in I-031 "
        "were checked against it, and from week 3 the fabric is derived from the "
        "BER Research Tool whose own validation runs through this axis. So "
        "PL-GAS-01, which scores against this table, is a CONSISTENCY "
        "check against a calibration input and NOT an independent "
        "validation - the held-out gas axis is DBERNG02 (dwelling type x "
        "period of construction), exposure 'none', which is what U31 "
        "uses. See I-058."
    ),
))

register(Source(
    key="cso.gas.dberng02_by_dwelling_construction",
    url=f"{_PXSTAT}/DBERNG02/JSON-stat/2.0/en",
    relpath="cso_electricity/DBERNG02_mean_gas_by_dwelling_and_construction.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland), from matched BER and Gas Networks Ireland meter data",
    title="Mean Gas Consumption by type of dwelling, period of construction and year (DBERNG02)",
    intended_use="calibration",
    model_development_exposure="none",
    used_for=(
        "The held-out half of the heating check, mirroring DBEREL02 exactly: "
        "dwelling type crossed with period of construction, an axis no fix was "
        "fitted to, and one D02 already carries as year_built_band. Keeping the "
        "same tuned/held-out split on both the gas and the electricity side is "
        "what lets the E1 report say whether the device and physics layers "
        "generalise rather than only that they were fitted. Exposure stays "
        "'none' and must stay 'none'."
    ),
))

register(Source(
    key="cso.housing.trs05_floor_area_by_authority",
    url=f"{_PXSTAT}/TRS05/JSON-stat/2.0/en",
    relpath="cso_housing/TRS05_median_floor_area_of_rental_properties.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland), from RTB tenancy registrations matched to BER",
    title="Total Floor Area of Rental Properties by local authority and year (TRS05)",
    intended_use="calibration",
    model_development_exposure="tuning",
    used_for=(
        "The only public Irish floor-area figure in PxStat, and the anchor for "
        "I-031. SAPS publishes room COUNTS and no areas, and neither EBA02 nor "
        "EBQ02 carries floor area, so the metres-squared-per-room relationship "
        "had to be assumed - and the assumption was wrong in a way that "
        "mattered: apartments were given MORE area per room than detached "
        "houses, which put the town's apartment median at 120.8 m2 against a "
        "detached median of 129.5. TRS05 gives 89.4 m2 as the median for Co. "
        "Cork rental properties in 2021. It bounds from BELOW rather than "
        "fixing the level, because rentals skew smaller and apartment-heavier "
        "than the whole stock, and that direction is stated wherever it is "
        "used. Cork County Council is the authority covering Cobh. TUNING-EXPOSED: the floor-area relationship was fixed against it, so it cannot validate floor area. PL-AREA-01 scores against NDA08 instead, which is exposure 'none'."
    ),
))

# --------------------------------------------------------------------------- #
# U27 plausibility references (week 2 step 1)
# --------------------------------------------------------------------------- #

register(Source(
    key="cso.appliances.has02_ownership",
    url=f"{_PXSTAT}/HAS02/JSON-stat/2.0/en",
    relpath="cso_plausibility/HAS02_household_appliance_ownership.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland), Survey on Income and Living Conditions",
    title="Households who possess a household appliance, by appliance type, possession status and year (HAS02)",
    intended_use="validation",
    model_development_exposure="none",
    used_for=(
        "U27 plausibility: appliance OWNERSHIP, which `OWNERSHIP_PRIORS` has "
        "carried as declared assumptions [A] since Day 5 with the note that "
        "'SAPS publishes no appliance ownership'. SAPS does not, but SILC "
        "does: HAS02 gives the share of households possessing a washing "
        "machine, clothes dryer, dishwasher, fridge, fridge with separate "
        "freezer, deep freeze and microwave. Seven of the nineteen priors stop "
        "being assumptions. Declared `validation` and exposure `none`: the "
        "priors were set before this table was found, so it can score them "
        "rather than merely agree with them. It must stay unexposed - if a "
        "prior is ever adjusted against it, its intended_use changes with it."
    ),
))

register(Source(
    key="cso.housing.nda08_new_dwelling_size_by_type",
    url=f"{_PXSTAT}/NDA08/JSON-stat/2.0/en",
    relpath="cso_plausibility/NDA08_average_new_dwelling_size_by_type.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="Average New Dwelling Size by dwelling type and year, with weight in mix (NDA08)",
    intended_use="validation",
    model_development_exposure="none",
    used_for=(
        "U27 plausibility: floor area BY DWELLING TYPE, which is what I-031 "
        "needed and TRS05 could not give - TRS05 is a rental median by local "
        "authority with no type split, and was used only as a lower bound. "
        "NDA08 gives square metres for single houses, scheme houses and "
        "apartments separately, plus each type's weight in the mix. New "
        "dwellings only, so it bounds the MODERN end of the stock and is the "
        "right comparator for the post-2005 cohort rather than for a pre-1980 "
        "terrace. Exposure `none` and it must stay so: the apartment area-per-"
        "room value was corrected against TRS05 and physical reasoning, not "
        "against this, so this can still score the correction."
    ),
))

# --------------------------------------------------------------------------- #
# U30 (9 Oct 2026): found by the sweep of every remaining [A] flag over the
# PxStat catalogue. Each is here because a declared assumption named a void
# that turned out not to be one. I-040's lesson, applied: the flag recorded a
# conclusion; the sweep records the search.
# --------------------------------------------------------------------------- #

# The table whose absence caused I-031. Room counts were drawn independently
# of dwelling type and bedrooms, which produced a 285.7 m2 three-bedroom
# apartment and 13.6 MWh of space heat. The fix was a feasibility-derived
# constant; this is the public JOINT - rooms x bedrooms x year built x
# dwelling type - from the same census year as T0, at county level, which can
# score it. Declared validation-only and exposure=none: the geometry was set
# before this was found, so it can judge it. Were a value ever tuned against
# it, this declaration changes with it.
register(Source(
    key="cso.census2022.f2063_rooms_bedrooms_year_type",
    url=f"{_PXSTAT}/F2063/JSON-stat/2.0/en",
    relpath="cso_housing/F2063_rooms_bedrooms_yearbuilt_accommodation_2022.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="Census 2022 F2063: private dwellings by number of rooms, number of bedrooms, year built, type of private accommodation and county",
    intended_use="validation",
    model_development_exposure="none",
    used_for=(
        "PL-ROOMS-01: scores the modelled rooms x bedrooms x dwelling-type "
        "joint against Census 2022 for Cork County. I-019 / I-031 / U30."
    ),
))

# I-011: the dwelling-type x heating-fuel split is an assumption because SAPS
# publishes the two marginals separately. Census 2011 publishes the joint.
register(Source(
    key="cso.census2011.cd488_heating_by_accommodation_and_period",
    url=f"{_PXSTAT}/CD488/JSON-stat/2.0/en",
    relpath="cso_housing/CD488_central_heating_by_accommodation_and_period_2011.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="Census 2011 CD488: private households by type of private accommodation, type of central heating and period built",
    intended_use="validation",
    model_development_exposure="none",
    substitute_flag=(
        "[A] retained: the joint is 2011, eleven years before T0, so it "
        "constrains the STRUCTURE (which fuels go with which dwelling type "
        "and era) and not the 2022 levels, which come from SAPS 2022"
    ),
    used_for=(
        "U30: the public joint behind I-011's assumed dwelling-type x "
        "heating-fuel split. To be used in the week 3 fabric and heating "
        "work, not before."
    ),
))

# I-040 found HAS02 (SILC, 7 appliances, to 2019). The Household Budget
# Survey publishes thirteen, and - this is the part HAS02 cannot do -
# publishes them BY HOUSEHOLD SIZE, which is exactly what the per_person
# slopes in OWNERSHIP_PRIORS assume. HS023's title is the single word
# "Households"; a title-only search cannot find it. Its dimension labels can.
register(Source(
    key="cso.appliances.hs023_hbs_appliances_urban_rural",
    url=f"{_PXSTAT}/HS023/JSON-stat/2.0/en",
    relpath="cso_plausibility/HS023_hbs_household_appliances_urban_rural.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="Household Budget Survey 2015 HS023: households possessing each of thirteen household appliances, by urban/rural location",
    intended_use="validation",
    model_development_exposure="none",
    used_for=(
        "PL-APPL-01 extension: the six appliance types HAS02 does not carry, "
        "of which `television` is modelled. U30."
    ),
))

register(Source(
    key="cso.appliances.hs219_hbs_appliances_by_household_size",
    url=f"{_PXSTAT}/HS219/JSON-stat/2.0/en",
    relpath="cso_plausibility/HS219_hbs_household_appliances_by_household_size.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="Household Budget Survey 2015 HS219: households possessing each of thirteen household appliances, by household size (1 to 6+ persons)",
    intended_use="validation",
    model_development_exposure="none",
    used_for=(
        "PL-APPLSIZE-01: scores the `per_person` ownership slopes, which were "
        "declared assumptions with the comment that 'the sub-linearity is not "
        "in doubt, only its slope'. This publishes the slope. U30."
    ),
))

# Life-course event rates (design 5.3 gives none). Marriage is the one
# transition published as a RATE by single year of age; separation and divorce
# appear only as census stocks, which are not transition rates.
register(Source(
    key="cso.vitalstats.vsa49_marriage_rates_by_age",
    url=f"{_PXSTAT}/VSA49/JSON-stat/2.0/en",
    relpath="cso_vitalstats/VSA49_marriage_rates_by_single_year_of_age.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="VSA49: marriage rates per 1,000 males and per 1,000 females by single year of age",
    intended_use="calibration",
    model_development_exposure="none",
    used_for=(
        "WP5 / week 2 step 5: the union-formation transition rate in the ten-"
        "year life course, which design 5.3 leaves as a declared assumption. "
        "U30."
    ),
))

# --------------------------------------------------------------------------- #
# I-039: the peak and load-factor reference.
#
# U30 established that PxStat has NOTHING on this - zero hits for peak demand,
# peak load, maximum demand, load factor, ADMD and after diversity across all
# 13,086 tables (I-043). It is published, but by the network operator rather
# than the statistics office.
#
# ESB Networks' Standard Load Profiles are the settlement profiles for the
# Irish retail market. LP1, "Urban Domestic 24 Hour", gives a Demand Energy
# Coefficient for every quarter-hour of the year, unitised to sum to 1.0 over
# the year - so the load factor and the peak-to-mean ratio come straight out of
# it with no assumption and no denominator from another source:
#
#     load factor = mean coefficient / peak coefficient
#
# The 2022 vintage is taken deliberately. T0 is 2022, and PL-AREA-01 was once
# found validating a 2022 town against NDA08's 2026 figure; a profile is also
# re-derived annually from measured data, so the year is a property of the
# reference and not a formality. Measured from this file: LP1 2022 has a load
# factor of 0.4129 and an annual peak quarter-hour 2.422x the annual mean.
#
# What it is NOT: an individual household's load factor. LP1 is the
# after-diversity profile of the whole urban domestic class, which is the right
# instrument for feeder loading (S11) and the wrong one for a single dwelling.
# A single household's peak needs smart-meter or sub-metered microdata, which
# in Ireland means CER/ISSDA, which the brief forbids. That half of PL-PEAK-01
# stays unsourced and I-043 records it.
register(Source(
    key="esbn.rmds.slp_indexes_2022",
    url=(
        "https://cdn.rmdservice.com/media/docs/default-source/references/"
        "standard-load-profiles/standard-load-profiles-2022/"
        "load-profiles-indexes-2022.xlsx?sfvrsn=a00f02e5_1"
    ),
    relpath="esbn_rmds/load-profiles-indexes-2022.xlsx",
    licence=RMDS_LICENCE,
    publisher="ESB Networks / Retail Market Design Service",
    title=(
        "ESB Networks Standard Load Profiles 2022: quarter-hourly Demand "
        "Energy Coefficients for LP1 Urban Domestic 24 Hour through LP9, "
        "unitised to sum to 1.0 over the year"
    ),
    intended_use="validation",
    model_development_exposure="none",
    used_for=(
        "PL-PEAK-01 (I-039): the after-diversity domestic load factor and "
        "peak-to-mean ratio, against which the aggregate feeder load of the "
        "simulated town is checked before S11."
    ),
))

# --------------------------------------------------------------------------- #
# U25: the anchor for domestic hot water, boiler losses and gas cooking.
#
# U30 searched the whole PxStat catalogue for hot water, water heating,
# immersion and cooking fuel and found ZERO hits for every one of them, so
# there is no CSO series to calibrate any of this against. The Irish reference
# is the regulatory methodology itself: SEAI's DEAP manual, which every Irish
# BER assessment is computed with.
#
# It is a PDF, so it is not machine-readable in the sense the other sources
# are, and the brief's rule for that case applies - record the value by hand
# with its citation. Each number taken from it is pinned in
# `data/deap_hot_water.yaml` with its table and section, and a test asserts
# the file's provenance fields point at this manifest. What the manual gives:
#
#   * Table 2    factors applied to losses for cylinders, thermal stores, CPSUs
#   * Table 2a   hot water storage vessel volume
#   * Table 3    primary circuit losses
#   * Table 3a   combi boiler losses, kWh/year
#   * Section 4  the DHW demand methodology (floor-area driven, after SAP 10),
#                the 6 L/min minimum for mixer showers, and the rule that
#                electric showers draw electricity directly rather than through
#                the water-heating system
#
# Declared `reference` rather than `calibration` for exposure purposes: it is a
# methodology document, and what is taken from it are published loss factors
# and definitions, not a fitted statistic.
register(Source(
    key="seai.deap.manual_4_2_7",
    url="https://www.seai.ie/sites/default/files/publications/DEAP_Manual.pdf",
    relpath="seai/DEAP_Manual_4_2_7.pdf",
    licence=SEAI_LICENCE,
    publisher="Sustainable Energy Authority of Ireland",
    title=(
        "Dwelling Energy Assessment Procedure (DEAP) Manual version 4.2.7: "
        "Section 4 domestic hot water, Table 2 cylinder loss factors, Table 3 "
        "primary circuit losses, Table 3a combi boiler losses"
    ),
    intended_use="reference",
    model_development_exposure="design",
    substitute_flag=(
        "[A] PDF, not machine-readable: values are transcribed by hand into "
        "data/deap_hot_water.yaml with their table and section, per the "
        "brief's rule for a reference that is not machine-readable"
    ),
    used_for=(
        "U25: domestic hot water demand, cylinder and primary-circuit losses, "
        "combi boiler losses, and the instantaneous-versus-stored distinction. "
        "Also the document I-019's BER band boundaries and DEAP primary-energy "
        "scope are to be read back from (sweep flag A-16). "
        "Week 3 step 1 additionally reads APPENDIX S from it for the fabric: "
        "Table S3's filled-cavity wall and Table S4's roof set what a "
        "retrofit achieves, and Tables S1/S2/S5 were used to check the era "
        "U-value table.\n\n"
        "EXPOSURE IS SECTION-LEVEL AND THE FIELD CANNOT SAY SO (I-061). "
        "The fabric retrofit U-values are DERIVED from Appendix S, which is a "
        "tuning use. PL-DHW-01 scores hot-water volume against Section 4's "
        "125 L/person/day, and that is NOT circular: D-043 built the demand "
        "from draw events tied to simulated activities rather than from "
        "DEAP's floor-area route, precisely so the model could disagree with "
        "it. The two uses read disjoint parts of a 213-page document. "
        "Exposure stays 'design' and the suite reports a "
        "design-exposed pass in its own category, neither fully independent "
        "nor a calibration input."
    ),
))

# U30's coverage test found this one, which is the lesson landing a third
# time. The earlier sweep searched `cooking fuel` and `gas cooking` and found
# nothing; the CSO's tables are titled "Main fuel used for cooking in
# households", so the words are there in the other order and a phrase search
# missed them. What caught it was not a person noticing but
# `test_every_a_flag_in_the_tree_is_accounted_for`: U25 added three new [A]
# flags, the coverage test demanded sweep entries for them, writing those
# entries demanded search terms, and the plain term `cooking` matched six
# tables.
#
# HEBEU34 is the urban/rural split, which is the right conditioning for a
# town of 14,000. Vintage 2024 against a T0 of 2022, which is the PL-AREA-01
# lesson and is why this is used for a STRUCTURAL share rather than a level.
register(Source(
    key="cso.cooking.hebeu34_cooking_fuel_urban_rural",
    url=f"{_PXSTAT}/HEBEU34/JSON-stat/2.0/en",
    relpath="cso_plausibility/HEBEU34_main_cooking_fuel_urban_rural.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title=(
        "HEBEU34: main fuel used for cooking in households, by urban/rural "
        "location and type of fuel (2024)"
    ),
    intended_use="calibration",
    model_development_exposure="tuning",
    substitute_flag=(
        "Published share is UNCONDITIONAL on having a gas connection; the "
        "model needs it conditional, so it is derived with one stated "
        "assumption rather than used directly"
    ),
    used_for=(
        "U25: the share of gas-connected dwellings that cook with gas, which "
        "was a declared assumption at 0.45 until this table was found. "
        "Replaces part of sweep flag A-33. TUNING-EXPOSED: the cooking-fuel split is derived from this table, so it cannot afterwards validate that split."
    ),
))

# The denominator for HEBEU34, from the same survey, the same year and the
# same urban/rural conditioning - which is why this table rather than SAPS:
# a conditional share computed across two different surveys would carry both
# their definitional differences.
register(Source(
    key="cso.cooking.hebeu106_heating_fuel_urban_rural",
    url=f"{_PXSTAT}/HEBEU106/JSON-stat/2.0/en",
    relpath="cso_plausibility/HEBEU106_main_heating_fuel_urban_rural.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title=(
        "HEBEU106: main fuel or energy source used to heat the home, by "
        "urban/rural location and type of fuel (2024)"
    ),
    intended_use="calibration",
    model_development_exposure="tuning",
    used_for=(
        "U25: the denominator that turns HEBEU34's unconditional cooking-fuel "
        "share into the conditional share the model needs - the share of "
        "GAS-CONNECTED dwellings that cook with gas. TUNING-EXPOSED: it is the "
        "denominator of a derived quantity and cannot validate it."
    ),
))

register(Source(
    key="cso.energy.sei01_energy_balance",
    url=f"{_PXSTAT}/SEI01/JSON-stat/2.0/en",
    relpath="cso_plausibility/SEI01_energy_balance.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland), from the SEAI national energy balance",
    title="Energy Balance by energy supply and consumption category, fuel type and year (SEI01)",
    intended_use="validation",
    model_development_exposure="none",
    used_for=(
        "U27 plausibility: the national residential energy balance by fuel, in "
        "ktoe. Gives the FUEL MIX of Irish household energy - how much is "
        "electricity against gas, oil, coal, peat and renewables - which is "
        "the one quantity that checks whether the simulated town's heating "
        "fuel shares and the relative size of its electricity and gas totals "
        "are jointly plausible. Every other reference checks one fuel at a "
        "time and so cannot see a town that gets both right separately and "
        "the balance between them wrong."
    ),
))


# --------------------------------------------------------------------------- #
# WP5 ten-year life course (week 2 step 5).
#
# Design 5.3 leaves every life-course hazard as a declared assumption. U30
# flag A-25 owns them and names this step. The searches that found these, and
# the searches that found nothing, are recorded in
# scripts/baile_nua/lifecourse/hazards.py SEARCH_RECORD - the rule from I-040
# is that an [A] flag records what was searched, not just that it is an
# assumption.
#
# What PxStat does NOT publish, after the searches in that record: a household
# in-migration or out-migration rate (only NET migration, EP006/PEB08); a
# separation or divorce transition rate (only census STOCKS, CD565); a
# retrofit rate (zero hits for "retrofit" across all 13,086 tables); a
# child-leaving-home hazard (only the age-20 stock, EA036).
# --------------------------------------------------------------------------- #

register(Source(
    key="cso.migration.ep006_net_migration_per_1000",
    url=f"{_PXSTAT}/EP006/JSON-stat/2.0/en",
    relpath="cso_lifecourse/EP006_net_migration_per_1000_by_county.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title=(
        "EP006: annual estimated net migration 1951-2016 per 1,000 of average "
        "population, by province, county or city"
    ),
    intended_use="calibration",
    model_development_exposure="none",
    used_for=(
        "WP5 move-in / move-out. This is a NET rate, so it constrains the "
        "DIFFERENCE between the two gross flows and not either one; the gross "
        "turnover rate is the [A] part (hazards.py A-25b)."
    ),
))

# U33, week 3 step 4. The Census question that bears on the move rate at last.
#
# A-25b's `retires_if` asked for "a published Irish gross in-migration or
# out-migration rate, as opposed to the net figure", and the sweep's verdict was
# that PxStat has none: EP006 and PEB08 publish NET migration, which is
# consistent with any pair of gross flows differing by that much. The verdict
# was right about migration ESTIMATES and wrong about where else to look.
#
# Census 2022 asks every resident where they usually lived one year before
# Census Day, and SAP2022 publishes the answer at TOWN level - so for Cobh
# itself, not for Cork County or the South-West. A person at a different address
# a year ago is an observed gross move, not a net balance. It is still a PROXY
# and not the hazard the model uses, for reasons recorded in A-25b and worth
# stating where the source is declared:
#
#   * it counts PEOPLE, and the model's hazard is per HOUSEHOLD. A household
#     that moves takes everyone with it, so the person rate is roughly the
#     household rate times mean household size, PLUS the individual moves that
#     do not move a household (a young adult leaving home). The conversion is
#     the [A] part;
#   * it counts moves INTO Cobh, because it asks where a current Cobh resident
#     used to live. The model's hazard is a move OUT. Those balance only in a
#     stationary population, which Cobh's is not quite;
#   * it is a one-year window observed once, so a year with unusual mobility is
#     not distinguishable from the long-run rate.
#
# It is nonetheless a far better bound than a net migration figure, and it is
# measured on the town the model is calibrated to.
# I-069's FIX. The age profile within each economic status, which SAPS does not
# publish and the population therefore could not use.
#
# This is the table that makes the conditional draw possible, and it is
# declared `tuning` because the population is BUILT from it. The search that
# led here is worth recording, because its result is the reason I-069 existed:
#
#   * every SAPS table crossing economic status is `Sex x Principal Economic
#     Status` - SAP2022T8T1SA, T8T1TOWN22, T8T1ED, T8T1CTY and their 2016 and
#     2011 editions. NOT ONE has an age dimension. So the small-area marginals
#     the population is fitted to genuinely cannot condition status on age, and
#     synthesise.py drawing status unconditionally was a faithful use of the
#     only small-area source there is;
#   * the age x status joint is published only at coarser geographies: FY047B
#     and FY048 by county, F7026 by single year of age nationally, F1054 by
#     settlement-size stratum, F7063 and F7133 nationally.
#
# FY047B is chosen over the others for two reasons that matter to the
# validation: its geography is Cork City and Cork County, which is Cobh's own,
# and its age bands SPLIT 15-19 from 20-24 where F1054 has a single 15-24 band.
# So fitting on FY047B and scoring on F1054 is not a coarsening of the scorer.
#
# WHAT THIS COSTS, stated here because it must not be discovered later: F1054
# and FY047B are the same Census cross-tabulated differently. After this fit,
# F1054 is held out as a TABLE and as a GEOGRAPHY, and it is NOT independent as
# a DATA SOURCE. What it still carries that FY047B does not is the
# settlement-size contrast - towns of 10,000 and over against the county as a
# whole - which is real and modest. F1054's exposure stays `none` because
# nothing is fitted to it; the strength of a pass against it is what changes,
# and I-069 records that rather than the register.
register(Source(
    key="cso.census.fy047b_economic_status_by_age_and_county",
    url=f"{_PXSTAT}/FY047B/JSON-stat/2.0/en",
    relpath=(
        "cso_population/"
        "FY047B_principal_economic_status_by_age_group_and_county.json"
    ),
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title=(
        "FY047B: population aged 15 years and over, by county and city, sex, "
        "principal economic status and age group"
    ),
    intended_use="calibration",
    model_development_exposure="tuning",
    used_for=(
        "I-069's fix. The age profile WITHIN each principal economic status "
        "for Cork City and Cork County, used to condition the "
        "economic-status draw on age in population/synthesise.py. SAPS "
        "publishes economic status by sex and small area and NEVER by age, so "
        "this is the only way the joint can be fitted at all. Exposure is "
        "`tuning` because the population is built from it, so it can never "
        "validate the population (7.1, I-058) - F1054 does that, held out."
    ),
))

# The nearest thing to an INDEPENDENT check on the age x status joint, and the
# search record for why nothing better exists.
#
# After F1054 was reclassified (it shares Census 2022 counts with the fit
# source FY047B), the catalogue was searched for a source that crosses age with
# economic status and is NOT Census 2022. Everything found falls into three
# groups and none is independent in the full sense:
#
#   * Census 2022, sharing counts with FY047B: F1054, FY047A/B, FY048, F7026,
#     F7063, F7133, F3048, F8048, F8050, SAP2022T8T1*. All ruled out.
#   * EARLIER CENSUSES, a different ENUMERATION of the same instrument:
#     CNA25 (1981-2016), C0703 (2011), B0503/A0503 (2002/1996). These cannot
#     share counts with Census 2022 because they are different data
#     collections, which is a real form of independence - and they share the
#     INSTRUMENT, self-assessed principal economic status, which is a real
#     limit on it.
#   * The wrong quantity: LFBA2 is ILO status but ends in 1997; NSA12/NSA13
#     are earnings by employment status; CDS23 and IEWA02 are disability
#     subsets; RPA03 covers ages 50-69 only.
#
# A current Labour Force Survey table crossing age with ILO status would be
# genuinely independent - different survey, different sample, different
# instrument - and the catalogue does not carry one at this cross.
#
# CNA25 2016 is therefore declared as the best available, with its limitation
# stated rather than glossed: it checks the STRUCTURE of the joint (nobody is
# retired at 20, students are young) which is stable across six years, and it
# cannot check the LEVEL, because a 2016-to-2022 difference confounds real
# change with model error.
register(Source(
    key="cso.census.cna25_economic_status_by_age_1981_2016",
    url=f"{_PXSTAT}/CNA25/JSON-stat/2.0/en",
    relpath=(
        "cso_population/CNA25_economic_status_by_age_group_1981_2016.json"
    ),
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title=(
        "CNA25: population aged 15 years and over by age group, principal "
        "economic status, sex and marital status, 1981 to 2016"
    ),
    intended_use="validation",
    model_development_exposure="none",
    used_for=(
        "Design 5.2. The nearest available INDEPENDENT check on the age x "
        "economic-status joint after F1054 was reclassified. A DIFFERENT "
        "ENUMERATION - Census 2016 - so it cannot share counts with the "
        "Census 2022 table the population is fitted to. It shares the "
        "INSTRUMENT (self-assessed principal economic status), and the "
        "six-year gap means it checks the STRUCTURE of the joint and not its "
        "LEVEL: a 2016-to-2022 difference confounds real change with model "
        "error. Exposure `none` and nothing is fitted to it."
    ),
))

# Design 5.2 joint validation, week 3. The PERSON-LEVEL joint of age and
# economic status.
#
# The existing joint checks (population/joint_metrics.py) are AREA-level: they
# compare correlations between small-area marginals - retired share against
# owner-occupied-no-mortgage share, unemployment against social renting. Those
# are real checks and they pass. They cannot see a person-level fault, and
# there is one: synthesise.py draws economic status from the area's marginal
# with no age conditioning above 15, so the marginal is matched and the JOINT
# is not. The town contains a 14-year-old retiree and 243 "students" with a
# median age of 45 (I-069).
#
# F1054 is the two-way joint itself and nothing else - Principal Economic
# Status by Age Group, Census 2022 - so it can be compared cell by cell
# against the synthesised population.
register(Source(
    key="cso.census.f1054_economic_status_by_age_group",
    url=f"{_PXSTAT}/F1054/JSON-stat/2.0/en",
    relpath="cso_population/F1054_principal_economic_status_by_age_group.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title=(
        "F1054: population aged 15 years and over, by principal economic "
        "status and age group"
    ),
    intended_use="validation",
    # RECLASSIFIED from `none` to `design` on 11 October 2026, and the reason
    # is measured rather than cautious. I-069's fix conditions the
    # economic-status draw on FY047B, and F1054 and FY047B are two partitions
    # of the SAME Census 2022 microdata:
    #
    #   F1054 'Ireland' 15+ total        4,136,852
    #   FY047B 'State'  15+ total        4,136,852   <- identical
    #
    # and each one's rows sum exactly to that total - F1054 partitions the
    # State by settlement type, FY047B by county. Cobh's own residents are
    # therefore counted in both: in F1054's "Towns 10,000 population and
    # over" row and in FY047B's "Cork City and Cork County" row. They share
    # underlying counts by construction.
    #
    # So a pass against F1054 after fitting to FY047B is NOT independent
    # evidence, and 7.1's rule applies: a source used to build the model
    # cannot validate it. `design` rather than `tuning` because F1054 itself
    # is not read by any model module - nothing is fitted to this table - but
    # its information is in the model through its sibling, and the
    # plausibility suite's `n_pass_against_a_design_exposed_reference` is
    # exactly the category for that.
    #
    # What it still carries that FY047B does not: the settlement-size
    # contrast, towns of 10,000 and over against the county as a whole. That
    # is real and modest, and it is not independence.
    model_development_exposure="design",
    used_for=(
        "Design 5.2 joint population validation. The person-level joint of "
        "age and principal economic status, compared cell by cell against the "
        "synthesised town. It found I-069: the population matched every "
        "marginal and had the joint wrong by a third.\n\n"
        "NOT INDEPENDENT since I-069's fix. It shares underlying Census 2022 "
        "counts with FY047B, which the population is now fitted to - proven "
        "by the identical 4,136,852 national 15+ total and by each table "
        "partitioning the State. A pass against it is a CONSISTENCY CHECK and "
        "belongs in the calibration-exposed table, not the independent one."
    ),
))

# WP7 venues, the third-level half. I-069's fix exposed it as a real gap
# rather than a symptom: the town's 19-and-over students fell from 241 with a
# median age of 45 to 91 starting at 19, which is a genuine third-level
# population that had nowhere to go.
#
# Cobh has no third-level institution. Its students commute to Cork, and EDA99
# publishes enrolment per INSTITUTION - including "National University of
# Ireland, Cork" - so the capacity of the venue they travel to is sourced
# rather than declared. That the venue sits outside the town is the modelled
# fact, not an approximation: a Cobh resident at UCC is out of the modelled
# town for the day, and their travel time comes from the Irish journey-time
# profile already declared for commuting.
register(Source(
    key="cso.education.eda99_third_level_enrolments_by_institution",
    url=f"{_PXSTAT}/EDA99/JSON-stat/2.0/en",
    relpath=(
        "cso_venues/EDA99_third_level_enrolments_by_institution.json"
    ),
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title=(
        "EDA99: students enrolled in and entrants to third level courses, by "
        "institution"
    ),
    intended_use="calibration",
    model_development_exposure="design",
    used_for=(
        "WP7 venues. Full-time enrolment at National University of Ireland, "
        "Cork, which sizes the college venue the town's 19-and-over students "
        "attend. Exposure `design` and not `none`: the venue capacity is "
        "DERIVED from it, so it can never afterwards validate venue "
        "occupancy (7.1, I-058)."
    ),
))

# WP7 venues, week 3. School SIZE is published and so is not declared.
#
# EDA49 gives the number of national schools AND the number of pupils in them,
# both broken down by the teacher size of the school, so the ratio is the
# published mean enrolment per size band - a real distribution of Irish primary
# school sizes rather than a capacity this build chose. That matters because
# design 9.4's week-3 acceptance criterion is "venue presence consistent with
# person presence", and a venue whose capacity was invented could be made
# consistent with anything by choosing the capacity.
#
# What EDA49 does NOT give, and stays [A] (A-50): how many schools Cobh has and
# where they are. PxStat publishes school statistics nationally; the register of
# individual schools is the Department of Education's, not the CSO's. So the
# COUNT of venues is derived from the town's own school-age population divided
# by the published mean size, and the siting is declared.
register(Source(
    key="cso.education.eda49_schools_and_pupils_by_teacher_size",
    url=f"{_PXSTAT}/EDA49/JSON-stat/2.0/en",
    relpath="cso_venues/EDA49_national_schools_and_pupils_by_teacher_size.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title=(
        "EDA49: national schools and pupils in national schools, by teacher "
        "size of school"
    ),
    intended_use="calibration",
    model_development_exposure="design",
    used_for=(
        "WP7 venues. Mean pupils per national school, from the published "
        "pupil count over the published school count, which sizes the town's "
        "school venues. Exposure is `design` and not `none`: the venue "
        "capacities are DERIVED from it, so it can never afterwards be used "
        "to validate them (7.1, I-058). The number of schools in Cobh and "
        "their siting stay [A] (A-50)."
    ),
))

register(Source(
    key="cso.census.sap2022_usual_residence_one_year_ago_by_town",
    url=f"{_PXSTAT}/SAP2022T2T3TOWN22/JSON-stat/2.0/en",
    relpath=(
        "cso_lifecourse/"
        "SAP2022T2T3TOWN22_usual_residence_one_year_ago_by_town.json"
    ),
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title=(
        "SAP2022T2T3TOWN22: usually resident population aged 1 year and over "
        "by usual residence 1 year before Census Day, by Towns 2022"
    ),
    intended_use="calibration",
    model_development_exposure="none",
    used_for=(
        "U33. A sourced PROXY for the gross household move rate, replacing the "
        "unmet internal-consistency criterion on `move_out` in "
        "lifecourse/tenyear.py's vital-statistics check. Cobh's own share of "
        "residents who were at a different address one year earlier. The "
        "person-to-household conversion stays [A] (A-25b): this bounds the "
        "hazard, it does not set it. Exposure stays `none` because nothing is "
        "fitted to it - the hazard keeps its declared value and this says "
        "whether that value is consistent with what the Census observed."
    ),
))

register(Source(
    key="cso.housing.vac17_vacancy_flows",
    url=f"{_PXSTAT}/VAC17/JSON-stat/2.0/en",
    relpath="cso_lifecourse/VAC17_vacancy_flows.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="VAC17: vacancy flows, quarterly (dwellings entering and leaving vacancy)",
    intended_use="calibration",
    model_development_exposure="none",
    used_for=(
        "WP5 vacancy chain. This is the one table that publishes vacancy as a "
        "FLOW rather than a stock, so it constrains the rate at which homes "
        "enter and leave vacancy - which is what a move-out/move-in chain "
        "actually generates."
    ),
))

register(Source(
    key="cso.housing.vac04_local_authority_vacancy_rates",
    url=f"{_PXSTAT}/VAC04/JSON-stat/2.0/en",
    relpath="cso_lifecourse/VAC04_local_authority_vacancy_rates.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="VAC04: local authority vacancy rates, quarterly",
    intended_use="calibration",
    model_development_exposure="none",
    used_for=(
        "WP5 vacancy chain: the Cork County equilibrium vacancy rate the ten-"
        "year run has to hold. Preferred over C0674, which is the 2006 census "
        "vintage."
    ),
))

register(Source(
    key="cso.housing.f2095_housing_stock_vacancy_by_ed",
    url=f"{_PXSTAT}/F2095/JSON-stat/2.0/en",
    relpath="cso_lifecourse/F2095_housing_stock_and_vacancy_rate_by_ed.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="F2095: housing stock and vacancy rate by electoral division (Census 2022)",
    intended_use="calibration",
    model_development_exposure="none",
    used_for=(
        "WP5 vacancy chain at the town's own geography: the Cobh electoral "
        "divisions, rather than the county or the state."
    ),
))

register(Source(
    key="cso.labour.jca01_job_churn_by_age_sex",
    url=f"{_PXSTAT}/JCA01/JSON-stat/2.0/en",
    relpath="cso_lifecourse/JCA01_job_churn_components_by_age_and_sex.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="JCA01: job churn components for employees by year, sex, age and employee status",
    intended_use="calibration",
    model_development_exposure="none",
    used_for=(
        "WP5 employment change. Job churn is published as a rate by AGE and "
        "SEX, which is what the life course needs; the census labour-force "
        "tables are stocks and give no transition rate at all."
    ),
))

register(Source(
    key="cso.energy.hebeu37_efficiency_installations",
    url=f"{_PXSTAT}/HEBEU37/JSON-stat/2.0/en",
    relpath="cso_lifecourse/HEBEU37_energy_efficiency_installations_in_the_home.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="HEBEU37: energy efficiency installations in place in the home, by type",
    intended_use="calibration",
    model_development_exposure="none",
    used_for=(
        "WP5 retrofit. This is a PREVALENCE of installations in place, not an "
        "adoption rate, so it bounds the ten-year cumulative total rather "
        "than the annual hazard (hazards.py A-25f). PxStat has no retrofit "
        "rate: zero hits for 'retrofit'."
    ),
))

register(Source(
    key="cso.health.hspae122_multiple_chronic_conditions",
    url=f"{_PXSTAT}/HSPAE122/JSON-stat/2.0/en",
    relpath="cso_lifecourse/HSPAE122_multiple_chronic_conditions_50_plus.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="HSPAE122: multiple chronic conditions among people aged 50 and over",
    intended_use="calibration",
    model_development_exposure="none",
    used_for=(
        "WP5 generic health states: the prevalence of a persistent health "
        "state at 50+, which the onset hazard has to reproduce as a stock. "
        "Under-50 onset is [A] (hazards.py A-25e)."
    ),
))


# Published BOUNDS for the WP5 hazards that have no published RATE. These are
# stocks, not transition rates, so they cannot drive an event; they constrain
# what the [A] hazard is allowed to produce over ten years. Fetching them
# turns "assumed, nothing found" into "assumed, and here is the published
# quantity it has to stay consistent with".

register(Source(
    key="cso.census.cd565_divorced_and_separated_population",
    url=f"{_PXSTAT}/CD565/JSON-stat/2.0/en",
    relpath="cso_lifecourse/CD565_divorced_and_separated_population.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title=(
        "CD565: divorced and separated population aged 15 and over by age "
        "group, sex and number of children in the household"
    ),
    intended_use="calibration",
    model_development_exposure="none",
    used_for=(
        "WP5 separation hazard BOUND (hazards.py A-25c). PxStat publishes no "
        "separation or divorce transition rate for Ireland; this is the "
        "resulting STOCK, which the assumed hazard has to reproduce."
    ),
))

register(Source(
    key="cso.census.ea036_age_20_living_with_parents",
    url=f"{_PXSTAT}/EA036/JSON-stat/2.0/en",
    relpath="cso_lifecourse/EA036_age_20_still_living_with_parents.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="EA036: population aged 20 still living with parents, 2011 to 2016",
    intended_use="calibration",
    model_development_exposure="none",
    used_for=(
        "WP5 child-leaving-home hazard BOUND (hazards.py A-25d). The only "
        "published quantity found is this single-age STOCK at 20; the hazard "
        "over ages 18-30 is assumed and has to pass through it."
    ),
))


# --------------------------------------------------------------------------- #
# WP6 calendar and events, S06 / D14 (week 2 step 6).
#
# R20's acceptance test is an event coverage audit: "every listed class present
# WITH A SOURCE". D14 lists ten kinds - holiday, school term, storm, outage,
# festival, cruise day, market, sport, roadworks, DST. Four of them have a
# published Irish source and are declared here; the rest are [A] with their
# search record in calendar_events.py EVENT_SEARCH_RECORD.
#
# Cobh is a cruise port, which is why TBA10 and TBA11 matter to this town
# specifically rather than generically: a cruise call puts several thousand
# visitors into a town of three thousand people for a day.
# --------------------------------------------------------------------------- #

register(Source(
    key="cso.tourism.tba10_cruise_visits_by_port",
    url=f"{_PXSTAT}/TBA10/JSON-stat/2.0/en",
    relpath="cso_events/TBA10_cruise_ships_and_passenger_visits_by_port.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="TBA10: cruise ships and passenger visits to Irish ports, by year and port",
    intended_use="calibration",
    model_development_exposure="none",
    used_for=(
        "WP6 'cruise day' event class: how many calls a year the Port of Cork "
        "takes and how many passengers they land, which sets the event's "
        "frequency and its footprint."
    ),
))

register(Source(
    key="cso.tourism.tba11_cruise_visits_by_month",
    url=f"{_PXSTAT}/TBA11/JSON-stat/2.0/en",
    relpath="cso_events/TBA11_cruise_ship_visits_by_month_of_arrival.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title="TBA11: cruise ship visits to Irish ports, by year and month of arrival",
    intended_use="calibration",
    model_development_exposure="none",
    used_for=(
        "WP6 'cruise day' SEASONALITY: the month-of-arrival distribution, so "
        "cruise days fall in the season they really fall in rather than "
        "uniformly across the year."
    ),
))

register(Source(
    key="cso.education.sca42_primary_absence_by_county",
    url=f"{_PXSTAT}/SCA42/JSON-stat/2.0/en",
    relpath="cso_events/SCA42_primary_school_absence_by_county.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title=(
        "SCA42: average percentage of primary school children absent, by year, "
        "county, DEIS status and school location"
    ),
    intended_use="calibration",
    model_development_exposure="none",
    used_for=(
        "WP6 school-term attendance BOUND. Read carefully: SCA42 is the share "
        "of children absent for TWENTY DAYS OR MORE in the school year, which "
        "is chronic absence and not a daily absence rate. It therefore bounds "
        "the daily school-day attendance probability from below rather than "
        "setting it; the daily rate is [A] (calendar_events.py A-41)."
    ),
))


# --------------------------------------------------------------------------- #
# Week 3 step 1: the fabric. I-048's retrofit hypothesis needed a source for
# the retrofit STATE of Irish dwellings, and PxStat has none - 18 search terms
# across all 13,086 tables return nothing (see physics/retrofit_state.py
# SEARCH_RECORD; the 14 hits for "wall" are all "wallet/purse").
#
# SEAI's National BER Research Tool is better than a share. It publishes the
# ASSESSED U-value of every element of every rated dwelling, with its year of
# construction and its BER band - so the era-to-U-value mapping can be
# validated against the real joint distribution rather than against an assumed
# penetration rate. 252 columns, about 1.5 GB of tab-separated text.
#
# CC-BY 4.0, listed on data.gov.ie, publisher SEAI. The download is an ASP.NET
# postback rather than a file URL, which is why Source.form_post exists.
#
# WHAT IT IS NOT. BER coverage is not a census - the project's own ber.py
# already records that it "over-represents recently assessed dwellings" - so
# its MARGINAL distribution over dwellings is biased. What is used here is the
# U-value CONDITIONAL on (year of construction, BER band, dwelling type), which
# that bias affects far less, and `TypeofRating` separates existing dwellings
# from new builds so the retrofit question can be asked of the right rows.
# --------------------------------------------------------------------------- #

register(Source(
    key="seai.ber.research_tool",
    url="https://ndber.seai.ie/BERResearchTool/ber/search.aspx",
    relpath="seai/BERPublicSearch.zip",
    licence="CC-BY 4.0 (data.gov.ie; publisher Sustainable Energy Authority of Ireland)",
    publisher="Sustainable Energy Authority of Ireland",
    title=(
        "National BER Research Tool: anonymised domestic BER dataset, with "
        "assessed element U-values, year of construction and BER band"
    ),
    intended_use="calibration",
    # TUNING-EXPOSED FOR FABRIC, and that is the whole point of recording it.
    #
    # The model's element U-values are DERIVED from this dataset's assessed
    # conditional (era x BER band). So it is a calibration input for fabric and
    # it can never afterwards serve as a validation reference for fabric: a
    # comparison of modelled against assessed U-values would come out at 1.0
    # by construction and would read as agreement.
    #
    # That also fixes the standing of the I-048 measurement. The 1.913 old /
    # 0.750 new divergence in v1/evidence/i048_fabric_assessed.json was taken
    # BEFORE this source influenced the model, which is what makes it a
    # finding. Re-running the same comparison after the derivation is wired in
    # is not a validation and must not be reported as one.
    #
    # What validates fabric instead: the GAS axis, which is independent of
    # this dataset. DBERNG01 (dwelling type x BER band) is the tuned
    # reference and DBERNG02 (dwelling type x period of construction) is held
    # out, with exposure "none", and U31 is evaluation-only. A fabric change
    # earns its keep by moving the gas ratio and the U31 gradient, not by
    # agreeing with the table it was built from.
    model_development_exposure="tuning",
    used_for=(
        "Week 3 step 1 / I-048: DERIVING the era-and-band-to-U-value mapping "
        "that data/fabric_u_values.yaml declared [A] and never read back. "
        "Gives the assessed U-value distribution conditional on year of "
        "construction and BER band, which is what the retrofit hypothesis is "
        "about - so no retrofit penetration RATE has to be assumed. "
        "TUNING-EXPOSED FOR FABRIC: not available to validate fabric. The "
        "independent fabric validation is gas (DBERNG01 tuned, DBERNG02 held "
        "out)."
    ),
    form_post={
        "hidden": ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"),
        "fields": {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "ctl00$DefaultContent$BERSearch$dfExcelDownlaod$DownloadAllData":
                "Download All Data",
        },
    },
))


# --------------------------------------------------------------------------- #
# D27: retail tariff STRUCTURE and MAGNITUDES, for a RECORD-ONLY dataset.
#
# Seven sources, declared for one dataset: `baile_nua.export.tariffs` writes
# D27 (tariffs and contracts), which is a record of what a supplier or an
# aggregator would hold and is NEVER an input. Nothing in the model is fitted
# to any of these, and no module under engine/, physics/, devices/ or
# behaviour/ may even import the module that reads them - which is asserted by
# `test_d27_the_engine_cannot_read_the_tariff` over the source tree. So
# `model_development_exposure` is `none` for all seven, and it is `none` in the
# strongest available sense: the layers that could be exposed cannot see the
# data at all.
#
# `intended_use` is `reference` throughout, for the same reason: a tariff rate
# shapes no parameter here. It is the content of an exported column.
#
# Five of the seven are PDFs. The project's rule for a reference that is not
# machine-readable (U05, and the DEAP manual's own substitute_flag) is that
# values are transcribed by hand WITH their page, and a test asserts the quoted
# figure is on that page of the declared file. That is what
# `export/tariffs.TARIFF_RATES` carries and what
# `test_d27_every_sourced_rate_is_in_its_cited_document` checks. The two CSO
# tables are JSON-stat and are read at export time like every other PxStat
# input.
#
# WHY A SUPPLIER'S OWN PRICE SHEET AND NOT A STATISTICAL TABLE. The retail
# market is price-deregulated, so no regulator publishes the unit rates: the
# CRU's own Energy Monitoring Report states the components of a bill by worked
# example, and the rates themselves exist only in suppliers' published price
# schedules. A published price schedule, dated and archived with its SHA-256,
# is therefore the primary source for a unit rate, and the CSO's published
# price series is the independent cross-check on the level.
# --------------------------------------------------------------------------- #

#: Electric Ireland publishes its residential price schedules as dated PDFs on
#: its own CDN. Re-use terms are not stated on the document, so the licence
#: field says so rather than assuming it is open - the treatment U05 gave SEAI
#: and the RMDS load profiles.
EI_LICENCE = (
    "Electric Ireland published residential price schedule; re-use terms not "
    "stated on the document, to be confirmed in WP1 (as U05 for SEAI and RMDS)"
)

#: The CRU publishes its decision and information papers openly on cru.ie.
#: Terms are not stated on the documents themselves.
CRU_LICENCE = (
    "Commission for Regulation of Utilities published decision and "
    "information papers; re-use terms not stated on the publication, to be "
    "confirmed in WP1"
)

_PDF_SUBSTITUTE = (
    "[A] PDF, not machine-readable: the figures used are transcribed by hand "
    "into export/tariffs.TARIFF_RATES with their page and the exact published "
    "wording, per the brief's rule for a reference that is not "
    "machine-readable, and a test asserts each quoted figure is on that page "
    "of this file"
)

register(Source(
    key="electricireland.priceplan.standard_elec_2022_05",
    url=(
        "https://prd-cdn.electricireland.ie/media/docs/default-source/"
        "price-plans/residential/2022/0522_pp_standard_elec.pdf"
    ),
    relpath="electric_ireland/0522_pp_standard_elec.pdf",
    licence=EI_LICENCE,
    publisher="Electric Ireland (ESB)",
    title=(
        "Electric Ireland Standard Electricity Price Plan incl. NightSaver, "
        "price schedule valid as of 1 May 2022: 24-hour and NightSaver "
        "day/night unit rates and urban and rural annual standing charges"
    ),
    intended_use="reference",
    model_development_exposure="none",
    substitute_flag=_PDF_SUBSTITUTE,
    used_for=(
        "D27's flat and day/night rate magnitudes and their standing charges. "
        "The schedule is dated 1 May 2022 and the estate-year run simulates "
        "2022, so the rates are contemporaneous with the simulated year, and "
        "Cobh is urban so the URBAN standing charge is the one used. "
        "EXPOSURE IS `none` AND CANNOT BECOME ANYTHING ELSE: D27 is a "
        "record-only dataset and the frozen engine is forbidden from importing "
        "the module that reads this file, so no parameter can be fitted to it "
        "even by accident."
    ),
))

register(Source(
    key="electricireland.priceplan.home_electric_plus_sst_2024_11",
    url=(
        "https://prd-cdn.electricireland.ie/media/docs/default-source/"
        "price-plans/residential/2024/1124_pp_he_plus_sst.pdf"
        "?sfvrsn=6e0a0879_2"
    ),
    relpath="electric_ireland/1124_pp_he_plus_sst.pdf",
    licence=EI_LICENCE,
    publisher="Electric Ireland (ESB)",
    title=(
        "Electric Ireland Home Electric+ Standard Smart Tariff Price Plan, "
        "price schedule valid as of 1 November 2024: day, night and peak unit "
        "rates, the published band hours, and urban and rural annual standing "
        "charges"
    ),
    intended_use="reference",
    model_development_exposure="none",
    substitute_flag=_PDF_SUBSTITUTE,
    used_for=(
        "D27's three-band time-of-use plan: the only part of the card that "
        "carries PUBLISHED band hours (Day 08:00-23:00 excluding peak, Night "
        "23:00-08:00, Peak 17:00-19:00) and a published peak rate. The 2022 "
        "standard price schedule states no band hours at all, so this is also "
        "where the day/night plan's night window comes from - a CROSS-PLAN "
        "carry, flagged as such in export/tariffs. "
        "VINTAGE: this schedule is dated November 2024 and the simulated year "
        "is 2022. A three-band domestic smart tariff was not a published plan "
        "in May 2022, so there is no contemporaneous sheet to use; the "
        "mismatch is recorded on the dataset rather than hidden. Exposure "
        "`none`, as above."
    ),
))

register(Source(
    key="cru.ceg.enduring_arrangements_cru202454",
    url=(
        "https://cruie-live-96ca64acab2247eca8a850a7e54b-5b34f62.divio-media."
        "com/documents/"
        "Clean_Export_Guarantee-Enduring_Arrangements_to_Remunerate_Customers_"
        "for_Microgenerati.pdf"
    ),
    relpath="cru/CRU202454_clean_export_guarantee_enduring_arrangements.pdf",
    licence=CRU_LICENCE,
    publisher="Commission for Regulation of Utilities (Ireland)",
    title=(
        "CRU202454: Clean Export Guarantee - Enduring Arrangements to "
        "Remunerate Customers for Microgeneration Exports, decision paper "
        "published 18 June 2024"
    ),
    intended_use="reference",
    model_development_exposure="none",
    substitute_flag=_PDF_SUBSTITUTE,
    used_for=(
        "D27's export rate. The CRU records that export tariffs offered by "
        "suppliers 'have generally ranged from circa 16c/kWh to 25c/kWh' and "
        "that the floor price of zero for flat-rate export tariffs is "
        "retained. So the EXISTENCE of an export payment, its published "
        "RANGE and its regulated FLOOR are all sourced; the single number on "
        "the card is the midpoint of the published range, by a stated rule. "
        "This replaces the DEAP manual's 'currently 0c', which predates the "
        "guarantee. Exposure `none`."
    ),
))

register(Source(
    key="cru.energy_monitoring_report_2022",
    url=(
        "https://cruie-live-96ca64acab2247eca8a850a7e54b-5b34f62.divio-media."
        "com/documents/Energy-Monitoring-Report.pdf"
    ),
    relpath="cru/CRU202389_energy_monitoring_report_2022.pdf",
    licence=CRU_LICENCE,
    publisher="Commission for Regulation of Utilities (Ireland)",
    title=(
        "CRU202389: Energy Monitoring Report for 2022, information paper "
        "published 13 July 2023, including the worked decomposition of a "
        "domestic electricity bill into unit rate, standing charge per day, "
        "PSO levy and VAT"
    ),
    intended_use="reference",
    model_development_exposure="none",
    substitute_flag=_PDF_SUBSTITUTE,
    used_for=(
        "The INDEPENDENT regulator check that D27's card is decomposed the "
        "way an Irish domestic bill actually is. The report's own worked "
        "example gives a unit rate, an annual consumption of 4,200 kWh, a "
        "standing charge of EUR 0.80 per day, the PSO levy and the VAT, and "
        "those five reconcile to the estimated annual bill it states - so the "
        "transcription can be arithmetically verified rather than trusted. "
        "Published by the regulator and not by a supplier, which is why it is "
        "the cross-check and not the rate source. Exposure `none`."
    ),
))

register(Source(
    key="esbn.connections.basis_of_charges",
    url=(
        "https://www.esbnetworks.ie/docs/default-source/publications/"
        "basis-of-charges-for-connection-to-the-distribution-system.pdf"
        "?sfvrsn=40acdfd9_14"
    ),
    relpath=(
        "esbn_connections/"
        "basis_of_charges_for_connection_to_the_distribution_system.pdf"
    ),
    licence=RMDS_LICENCE,
    publisher="ESB Networks Ltd, approved by the CER (now the CRU)",
    title=(
        "ESB Networks Ltd, Basis of Charges for Connection to the "
        "Distribution System, revision 1, effective 8 February 2010: the "
        "standard domestic connection capacities and the definition of "
        "Maximum Import Capacity"
    ),
    intended_use="reference",
    model_development_exposure="none",
    substitute_flag=_PDF_SUBSTITUTE,
    used_for=(
        "D27's max_import_kw. The document states that 'Domestic connections "
        "are only available for the standard capacities of 3kVA, 12kVA, "
        "16kVA, 20kVA and 29kVA' and treats 12kVA as the standard domestic "
        "connection, so the connection capacity on the card is a published "
        "figure rather than a round guess. It is published in kVA and the "
        "schema declares the field in kW; the conversion at unity power "
        "factor is stated on the dataset rather than left implicit. Exposure "
        "`none`."
    ),
))

register(Source(
    key="cso.electricity.hebeu88_tariff_type_by_urban_rural",
    url=f"{_PXSTAT}/HEBEU88/JSON-stat/2.0/en",
    relpath="cso_electricity/HEBEU88_electricity_tariff_type_by_urban_rural.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title=(
        "HEBEU88: electricity tariff used by households for billing, by "
        "urban or rural location and type of electricity tariff (2024)"
    ),
    intended_use="reference",
    model_development_exposure="none",
    used_for=(
        "D27's PLAN MIX. The published categories are 'Standard tariff', "
        "'Day/Night tariff or Day/Night/Weekend tariff', 'Smart tariff', "
        "'Other tariff NEC' and 'Tariff type unknown', which map onto the "
        "three tariff_kind values datasets.yaml declares (flat, day-night, "
        "ToU). Cobh is urban, so the URBAN row is the one used, and the "
        "shares are renormalised over the three known categories with the "
        "suppressed and unknown shares reported rather than reassigned. "
        "Closes the assumption that the mix was an equal three-way split: "
        "this is the HAS02 lesson (I-040) again - the search over the "
        "declared PxStat catalogue found a published table where a comment "
        "had recorded a conclusion. Exposure `none`."
    ),
))

register(Source(
    key="cso.electricity.tmegb03_residential_electricity_prices",
    url=f"{_PXSTAT}/TMEGB03/JSON-stat/2.0/en",
    relpath="cso_electricity/TMEGB03_residential_electricity_prices.json",
    licence=CSO_LICENCE,
    publisher="Central Statistics Office (Ireland)",
    title=(
        "TMEGB03: residential electricity prices in euro per kWh, by year, "
        "semester, pricing basis and Eurostat household electricity "
        "consumption band (DA to DE)"
    ),
    intended_use="reference",
    model_development_exposure="none",
    used_for=(
        "The INDEPENDENT level check on D27's unit rates. Band DC is 2,500 "
        "to 5,000 kWh a year, which is where an Irish domestic meter sits, "
        "and the series is published per semester, so the 2022 half-year "
        "prices bracket the supplier's own 1 May 2022 schedule. Published by "
        "the CSO and not by the supplier whose rates are on the card, which "
        "is what makes it a check rather than a restatement. Exposure `none`."
    ),
))
