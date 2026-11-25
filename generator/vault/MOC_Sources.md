---
type: "index"
id: "MOC_Sources"
status: "generated"
tags:
  - "index"
  - "moc"
manifests: 80
register_rows: 76
generated_by: "scripts/build_vault.py"
---

# MOC — Sources

80 source manifests under `sources/`; 76 rows in the register `sources/SOURCES.md`.

## Rules the register applies

- Public data only.
- CER/ISSDA and any licensed or restricted source is NOT used.
- No calibration number is hard-coded from memory.
- Raw files are read-only after download.

## cru

| source | publisher | use | exposure | sha256 | datasets |
|---|---|---|---|---|---|
| [[cru.ceg.enduring_arrangements_cru202454]] | Commission for Regulation of Utilities (Ireland) | reference | none | `385df3ff9602…` | [[D27]] |
| [[cru.energy_monitoring_report_2022]] | Commission for Regulation of Utilities (Ireland) | reference | none | `418b4bc8b3c5…` | [[D27]] |

## cso

| source | publisher | use | exposure | sha256 | datasets |
|---|---|---|---|---|---|
| [[cso.babynames.boys]] | Central Statistics Office (Ireland) | calibration | none | `5e8a40708dea…` | [[D05]] |
| [[cso.babynames.girls]] | Central Statistics Office (Ireland) | calibration | none | `bd72b96a02bc…` | [[D05]] |
| [[cso.pxstat.collection]] | Central Statistics Office (Ireland) | reference | design | `5335948ac4d0…` | — |
| [[cso.saps2022.bua]] | Central Statistics Office (Ireland) | calibration | none | `eae400498565…` | — |
| [[cso.saps2022.ed]] | Central Statistics Office (Ireland) | reference | none | `09cbacb35a4c…` | — |
| [[cso.saps2022.glossary]] | Central Statistics Office (Ireland) | reference | none | `014a3c74a538…` | — |
| [[cso.saps2022.small_area]] | Central Statistics Office (Ireland) | calibration | none | `15f30f13a7ec…` | — |
| [[osi.small_areas_2022.cobh]] | Ordnance Survey Ireland / Tailte Éireann (via OSi Open Data) | calibration | none | `2c84ed0b5120…` | — |

## cso_electricity

| source | publisher | use | exposure | sha256 | datasets |
|---|---|---|---|---|---|
| [[cso.electricity.dbere101_by_dwelling_ber]] | Central Statistics Office (Ireland), from matched BER and … | calibration | tuning | `d0082edfdcfd…` | [[D24]] |
| [[cso.electricity.dbere102_by_dwelling_construction]] | Central Statistics Office (Ireland), from matched BER and … | calibration | none | `9b03f68ba15b…` | [[D02]] |
| [[cso.electricity.hebeu88_tariff_type_by_urban_rural]] | Central Statistics Office (Ireland) | reference | none | `1ce1d554a4d4…` | [[D27]] |
| [[cso.electricity.mec03_by_county_sector]] | Central Statistics Office (Ireland), from ESB Networks | reference | none | `858c6f76b918…` | — |
| [[cso.electricity.mec05_by_tariff_group]] | Central Statistics Office (Ireland), from ESB Networks | reference | none | `d91a0397387e…` | — |
| [[cso.electricity.mec06_residential_meters]] | Central Statistics Office (Ireland), from ESB Networks | reference | none | `660f479db3bf…` | — |
| [[cso.electricity.mec07_meters_by_county]] | Central Statistics Office (Ireland), from ESB Networks | calibration | none | `416f7db8540b…` | — |
| [[cso.electricity.tmegb03_residential_electricity_prices]] | Central Statistics Office (Ireland) | reference | none | `33a5bda1bec2…` | [[D27]] |
| [[cso.gas.dberng01_by_dwelling_ber]] | Central Statistics Office (Ireland), from matched BER and … | calibration | tuning | `1014220a5660…` | [[D24]] |
| [[cso.gas.dberng02_by_dwelling_construction]] | Central Statistics Office (Ireland), from matched BER and … | calibration | none | `39dd29fe62df…` | [[D02]] |

## cso_events

| source | publisher | use | exposure | sha256 | datasets |
|---|---|---|---|---|---|
| [[cso.education.sca42_primary_absence_by_county]] | Central Statistics Office (Ireland) | calibration | none | `1942e3fbbb7f…` | — |
| [[cso.tourism.tba10_cruise_visits_by_port]] | Central Statistics Office (Ireland) | calibration | none | `c5e7be83b473…` | — |
| [[cso.tourism.tba11_cruise_visits_by_month]] | Central Statistics Office (Ireland) | calibration | none | `6dc532da2f0e…` | — |

## cso_housing

| source | publisher | use | exposure | sha256 | datasets |
|---|---|---|---|---|---|
| [[cso.census2011.cd488_heating_by_accommodation_and_period]] | Central Statistics Office (Ireland) | validation | none | `b544bb57ae80…` | — |
| [[cso.census2022.f2063_rooms_bedrooms_year_type]] | Central Statistics Office (Ireland) | validation | none | `a3120181bd4c…` | — |
| [[cso.housing.trs05_floor_area_by_authority]] | Central Statistics Office (Ireland), from RTB tenancy … | calibration | tuning | `69b76b7a1ecf…` | — |

## cso_lifecourse

| source | publisher | use | exposure | sha256 | datasets |
|---|---|---|---|---|---|
| [[cso.census.cd565_divorced_and_separated_population]] | Central Statistics Office (Ireland) | calibration | none | `0d709de70e74…` | — |
| [[cso.census.ea036_age_20_living_with_parents]] | Central Statistics Office (Ireland) | calibration | none | `418b6dd2540e…` | — |
| [[cso.census.sap2022_usual_residence_one_year_ago_by_town]] | Central Statistics Office (Ireland) | calibration | none | `bb6f439d3e75…` | — |
| [[cso.energy.hebeu37_efficiency_installations]] | Central Statistics Office (Ireland) | calibration | none | `6dd7abc202b8…` | — |
| [[cso.health.hspae122_multiple_chronic_conditions]] | Central Statistics Office (Ireland) | calibration | none | `d2d889d27311…` | — |
| [[cso.housing.f2095_housing_stock_vacancy_by_ed]] | Central Statistics Office (Ireland) | calibration | none | `1ff9b70b7479…` | — |
| [[cso.housing.vac04_local_authority_vacancy_rates]] | Central Statistics Office (Ireland) | calibration | none | `128c46b52fe7…` | — |
| [[cso.housing.vac17_vacancy_flows]] | Central Statistics Office (Ireland) | calibration | none | `addd23677d7f…` | — |
| [[cso.labour.jca01_job_churn_by_age_sex]] | Central Statistics Office (Ireland) | calibration | none | `0d2cfedc88b2…` | — |
| [[cso.migration.ep006_net_migration_per_1000]] | Central Statistics Office (Ireland) | calibration | none | `f722628d7c63…` | — |

## cso_plausibility

| source | publisher | use | exposure | sha256 | datasets |
|---|---|---|---|---|---|
| [[cso.appliances.has02_ownership]] | Central Statistics Office (Ireland), Survey on Income and … | validation | none | `a879f0945593…` | — |
| [[cso.appliances.hs023_hbs_appliances_urban_rural]] | Central Statistics Office (Ireland) | validation | none | `9e93e4376c5a…` | — |
| [[cso.appliances.hs219_hbs_appliances_by_household_size]] | Central Statistics Office (Ireland) | validation | none | `fe48ac1242ce…` | — |
| [[cso.cooking.hebeu106_heating_fuel_urban_rural]] | Central Statistics Office (Ireland) | calibration | tuning | `d24b840fee50…` | — |
| [[cso.cooking.hebeu34_cooking_fuel_urban_rural]] | Central Statistics Office (Ireland) | calibration | tuning | `d0a2064ee4f3…` | — |
| [[cso.energy.sei01_energy_balance]] | Central Statistics Office (Ireland), from the SEAI national … | validation | none | `1ea0736fe45f…` | — |
| [[cso.housing.nda08_new_dwelling_size_by_type]] | Central Statistics Office (Ireland) | validation | none | `7b415941fa60…` | — |

## cso_population

| source | publisher | use | exposure | sha256 | datasets |
|---|---|---|---|---|---|
| [[cso.census.cna25_economic_status_by_age_1981_2016]] | Central Statistics Office (Ireland) | validation | none | `15ba6302037b…` | — |
| [[cso.census.f1054_economic_status_by_age_group]] | Central Statistics Office (Ireland) | validation | design | `29981f29a949…` | — |
| [[cso.census.fy047b_economic_status_by_age_and_county]] | Central Statistics Office (Ireland) | calibration | tuning | `6364fd592824…` | — |

## cso_venues

| source | publisher | use | exposure | sha256 | datasets |
|---|---|---|---|---|---|
| [[cso.education.eda49_schools_and_pupils_by_teacher_size]] | Central Statistics Office (Ireland) | calibration | design | `1a6d0f366364…` | — |
| [[cso.education.eda99_third_level_enrolments_by_institution]] | Central Statistics Office (Ireland) | calibration | design | `433ce54d0bd9…` | — |

## cso_vitalstats

| source | publisher | use | exposure | sha256 | datasets |
|---|---|---|---|---|---|
| [[cso.population.pea01_population_estimates_by_age_sex]] | Central Statistics Office (Ireland) | calibration | none | `1a45b0d605dc…` | — |
| [[cso.vitalstats.vsa08_deaths_by_age_and_sex]] | Central Statistics Office (Ireland) | calibration | none | `a54a0f9f29bf…` | — |
| [[cso.vitalstats.vsa104_fertility_rates_by_age]] | Central Statistics Office (Ireland) | calibration | none | `e79fc5add094…` | — |
| [[cso.vitalstats.vsa36_births_by_age_and_parity]] | Central Statistics Office (Ireland) | calibration | none | `bce58378ddc9…` | — |
| [[cso.vitalstats.vsa49_marriage_rates_by_age]] | Central Statistics Office (Ireland) | calibration | none | `d2492e760959…` | — |

## electric_ireland

| source | publisher | use | exposure | sha256 | datasets |
|---|---|---|---|---|---|
| [[electricireland.priceplan.home_electric_plus_sst_2024_11]] | Electric Ireland (ESB) | reference | none | `4da1616fc352…` | [[D27]] |
| [[electricireland.priceplan.standard_elec_2022_05]] | Electric Ireland (ESB) | reference | none | `5a717ae9df27…` | [[D27]] |

## esbn_connections

| source | publisher | use | exposure | sha256 | datasets |
|---|---|---|---|---|---|
| [[esbn.connections.basis_of_charges]] | ESB Networks Ltd, approved by the CER (now the CRU) | reference | none | `e7d1fc8ed317…` | [[D27]] |

## esbn_rmds

| source | publisher | use | exposure | sha256 | datasets |
|---|---|---|---|---|---|
| [[esbn.rmds.slp_indexes_2022]] | ESB Networks / Retail Market Design Service | validation | none | `a4e010ab8969…` | — |

## eurostat

| source | publisher | use | exposure | sha256 | datasets |
|---|---|---|---|---|---|
| [[eurostat.codelist.acl00]] | Eurostat | reference | none | `a380e29dae9d…` | — |
| [[eurostat.hetus.tus_00age]] | Eurostat | calibration | none | `45a58ae865e0…` | — |
| [[eurostat.hetus.tus_00hhstatus]] | Eurostat | calibration | none | `d637b6677c98…` | — |
| [[eurostat.hetus.tus_00selfstat]] | Eurostat | calibration | none | `79008d3d0386…` | — |
| [[eurostat.hetus.tus_00startime]] | Eurostat | calibration | tuning | `b681d632fd0f…` | — |
| [[eurostat.hetus.tus_00week]] | Eurostat | calibration | none | `41a2408f2308…` | — |

## met_eireann

| source | publisher | use | exposure | sha256 | datasets |
|---|---|---|---|---|---|
| [[met.cork_airport.hourly]] | Met Éireann | calibration | none | `8d592587f0c8…` | [[D31]] |
| [[met.roches_point.hourly]] | Met Éireann | calibration | none | `b1988d68f1d6…` | [[D15]] |

## seai

| source | publisher | use | exposure | sha256 | datasets |
|---|---|---|---|---|---|
| [[cso.ber.eba02_by_county]] | Central Statistics Office (Ireland), from the SEAI BER … | calibration | none | `031f0fcf64cd…` | [[D02]] |
| [[cso.ber.ebq02_renewables]] | Central Statistics Office (Ireland), from the SEAI BER … | calibration | none | `4ab2045e6714…` | [[D04]] |
| [[seai.ber.research_tool]] | Sustainable Energy Authority of Ireland | calibration | tuning | `1cf9b515c8b2…` | — |
| [[seai.deap.manual_4_2_7]] | Sustainable Energy Authority of Ireland | reference | design | `e2aee5b29399…` | — |

## unfiled

| source | publisher | use | exposure | sha256 | datasets |
|---|---|---|---|---|---|
| [[cso.census2016.saps2016_sa2017]] | Central Statistics Office (Ireland) / Ordnance Survey … | D-106 / Phase 4: the pre-2022 census base for the 1 Jan 2015 starting state, and the out-of-sample target for the Census 2022 checkpoint at G4. 18,641 small areas, 802 columns; 47 of the town's 53 small areas match directly on GEOGID. | design | `a951dfe8d542…` | — |
| [[cso.census2016.saps_2016_glossary]] | Central Statistics Office (Ireland) / Ordnance Survey … | Required to interpret SAPS2016_SA2017.csv; the column headers are not self-describing. | design | `4764547e47dd…` | — |
| [[cso.cpi.cpm18_liquid_fuels_home_heating_oil]] | Central Statistics Office (Ireland) | CROSS-CHECK on the EU Oil Bulletin. 276 months; item at position 103 of 234; statistic 'Consumer Price Index'. Agreement over the 132 common months 2015-2025: Pearson r 0.9949 on levels, Spearman rho 0.9928, r 0.9313 on month-over-month changes. NOTE the peak months differ: bulletin 2022-03, CPM18 2022-06. | tuning | `b59b82c82339…` | — |
| [[derived.esbn_smart_meter_rollout]] | derived in-project from ESB Networks press releases | Phase 12 / D18 era gating: a home has smart-meter interval data only from its install date. | design | `e4eca27f2eb3…` | — |
| [[derived.school_breaks_2014_2026]] | Department of Education (Ireland); extracted in-project | Phase 2: per-year school-term tables replacing SCHOOL_TERMS_2022. | design | `6b622cd1c375…` | — |
| [[ec.oil_bulletin.ie_heating_gas_oil_weekly]] | European Commission, DG Energy (extracted in-project) | 597 weekly observations, ZERO nulls. Peak 2022-03-14 at 1643.3 EUR/1000L (two weeks after the invasion of Ukraine); trough 2020-05-11 at 468.1 (the COVID crash). A 3.5x range across the window. | tuning | `5730daae6eba…` | — |
| [[ec.oil_bulletin.prices_history]] | European Commission, DG Energy | PRIMARY heating oil price for Phase 13. Ireland heating gas oil, consumer price with taxes, is column IE_price_with_tax_heating_oil on the 'Prices with taxes' sheet, EUR per 1000 L, weekly. | tuning | `03a95c7a42ab…` | — |
| [[esri.wp824.price_elasticity_residential_gas]] | Economic and Social Research Institute (ESRI), Dublin | D-117 / D18: the sourced Irish short-run price elasticity of residential heating demand, calibrating Phase 13's crisis response. | tuning | `6e3b26275c04…` | — |
| [[gaa.all_ireland_finals.2015_2026]] | compiled in-project from per-final match reports and … | A-43 partial reversal: inter-county All-Ireland finals only, as dated televised-event load drivers. Club fixtures remain dropped - no open-data fixture list exists. | none | `191f8d7bca48…` | — |
| [[osi.boundaries.small_areas_generalised_20m_2015]] | Central Statistics Office (Ireland) / Ordnance Survey … | Phase 4: small-area geography for the 2015 base. 18,641 polygons in WGS84, carrying SMALL_AREA, EDNAME, COUNTYNAME and AREA. The town's 47 matched areas sit in EDs 'Cobh Rural' and 'Cobh Urban', Cork County. | design | `0386592386c5…` | — |
| [[wrc.public_holidays]] | Workplace Relations Commission (Ireland) | Phase 2: the STATUTORY RULES for Ireland's 10 public holidays, plus an explicit 2026 date anchor, used to derive and verify per-year tables 2015-2026. | design | `c77985d614e4…` | — |

## Manifests with no row in `sources/SOURCES.md`

[[cso.census2016.saps2016_sa2017]], [[cso.census2016.saps_2016_glossary]], [[cso.cpi.cpm18_liquid_fuels_home_heating_oil]], [[derived.esbn_smart_meter_rollout]], [[derived.school_breaks_2014_2026]], [[ec.oil_bulletin.ie_heating_gas_oil_weekly]], [[ec.oil_bulletin.prices_history]], [[esri.wp824.price_elasticity_residential_gas]], [[gaa.all_ireland_finals.2015_2026]], [[osi.boundaries.small_areas_generalised_20m_2015]], [[wrc.public_holidays]]

## Register rows with no manifest on disk

`calibration`, `design`, `none`, `reference`, `selection`, `tuning`, `validation`
