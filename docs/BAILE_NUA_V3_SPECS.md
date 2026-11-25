# Baile Nua v3 (HRSD_Occupants): Specification

**Version:** 0.1 (draft for planning; not started) · **Date:** 21 October 2026 · **Owner:** Brian O'Regan, EIG, Tyndall National Institute, UCC
**Builds on:** `BAILE_NUA_V2_SPECS.md` (v2 fast track; v2.1 adds the ISSDA sets and GB LV feeder data).
**Primary consumers:** MLM-RD; O-CEI privacy-preserving edge models (boundary testing).

---

## 0. Why v3

v2 makes the town's **energy** real: about 95 % of electricity demand is measured donor energy. But the donors are British (London 2011-14, Edinburgh 2016-18, GB EV trial). v2.1 adds Irish household load (CER 2009-10) and Irish routines (TUS 2005), both old.

v3 has one aim: **make the town Irish-real and current**, measured in Ireland and, where possible, in or near Cork.

| Goal | Meaning |
|---|---|
| **G1 Irish consumption** | Each home's annual and seasonal electricity and gas follow real Irish households of the same dwelling, BER and household type (2016-2024) |
| **G2 Irish behaviour** | Occupancy, travel, remote work and EV use follow current Irish surveys, not UK or 2005 sources |
| **G3 In-place measurements** | A small set of real, consented homes near Cork, plus area-level network data for Cobh |
| **G4 A changing population** | Households form, move, grow and shrink as observed in Ireland 2016-2022 |
| **G5 Honest provenance** | Every row keeps its class (R1 to S) and every CSO-derived output passes CSO output checking |

---

## 1. Sources

### 1.1 CSO Research Microdata Files (one ROSA route; fit-only, outputs CSO-checked)

Register: https://www.cso.ie/en/aboutus/lgdp/csodatapolicies/dataforresearchers/rmfregister/

| Priority | RMF | Years | What it adds |
|---|---|---|---|
| 1 | **BER Energy** | 2016-2024 | Census 2022 households linked to BER and **quarterly electricity and gas use**: real Irish consumption by dwelling type, BER, fuel and household; the BER performance gap; replaces the 0.78 donor-vs-CSO rescaling question with a fitted answer |
| 1 | **Census BER Energy (COP BER)** | 2022 | The same with Census household attributes: joint distribution of household composition, dwelling and real energy use |
| 2 | **National Travel Survey** | 2021 | Journeys, modes, purposes, times and EV use: occupancy timing, car availability, EV charging times |
| 2 | **POWSCCAR** | 2022 | Commute origin, destination, mode and departure band by small area (moved here from v2.1: same ROSA application) |
| 3 | **SILC_ENERGY** | 2003-present | Energy poverty, arrears and affordability: under-heating, setpoint and rationing behaviour by household type |
| 3 | **Census Longitudinal Dataset** | 2016, 2022 | Household change and moves: the life-course layer (D03, D09, D20) |
| 3 | **Personal Work Life Balance Survey** | 2021 Q3 | Remote and flexible working: daytime occupancy by occupation and household |
| 4 | **HBS** | 2022-23 | Appliance ownership and household composition (also requested via ISSDA for earlier waves) |
| 4 | **QNHS environmental behaviours module** | 2014 | Household energy habits and environmental awareness |
| 4 | **ICT household** | 2022-23 | Smart-device and digital uptake: consent and sensor-tier propensities |
| 4 | **Vital Statistics** | 2007-present | Births and deaths by area and age for the life course |

### 1.2 In-place and Irish measurements (new agreements)

| Source | What | Route | Use |
|---|---|---|---|
| **Consented real homes** (30-100 near Cork) | Half-hourly smart-meter files households download from ESB Networks, plus a short survey | Recruitment (pilot sites, CO-OP), UCC ethics and GDPR | R1 Irish household load measured in place; validation homes |
| **Brian's NILM dataset** | Irish appliance-level traces | UCC/Tyndall background IP | Irish appliance cycle library |
| **O-CEI / ODEON / PARA//EL / ALF pilot data** (if consented) | Edge sensors, room climate, appliances | Project data agreements | Irish indoor climate and edge-data anchors |
| **ESB Networks SCADA** | Primary substation and MV feeders supplying Cobh, 15-30 min | Research agreement | V: real aggregate demand for the area; network calibration |

### 1.3 Carried from v2.1

ISSDA (CER smart-meter trials, TUS 2005, HBS), GB LV feeder data (SSEN, UKPN, Weave, NGED), SERL via a UK partner, and a newer Irish time-use survey if the CSO publishes one.

---

## 2. Methods

1. **Irish consumption anchor (BER Energy).** Fit the joint distribution of quarterly electricity and gas by dwelling type, BER band, fuel, floor area and household size. Use it to (a) choose and weight donors, (b) set each home's quarterly energy envelope, and (c) replace hand-set heating knobs with fitted ones. Donor half-hourly shape stays R2; quarterly totals become C1 fitted to Irish data.
2. **Irish behaviour.** Refit activity timing, departures and returns from NTS 2021 and POWSCCAR 2022 (Cobh small areas), remote-work days from PWLB 2021, and EV ownership, use and charging from NTS plus CSO vehicle licensing.
3. **Affordability.** Use SILC_ENERGY to give low-income and energy-poor households realistic under-heating and rationing.
4. **Living town.** Household transitions (formation, moves, births, deaths) from the Census Longitudinal Dataset and Vital Statistics; asset adoption already in v2.
5. **In-place homes.** Consented Cork homes enter as R1 donors for matched synthetic homes and as a held-out validation panel. They are never published at household level.
6. **Area validation.** Town aggregate vs ESB Networks SCADA for the Cobh feeders (scaled); feeder loading vs matched GB LV feeders.

---

## 3. Provenance targets (estimates, by rows)

| Class | v2 (est.) | v2.1 (est.) | **v3 (est.)** |
|---|---:|---:|---:|
| Real (R1 + R2 + R3) | 20-30 % | 20-30 % | **30-45 %**, with an Irish, in-place share for the first time |
| Calibrated (C1) | 1-3 % | 15-20 % | **25-35 %** |
| Computed (C2) | 50-60 % | 45-55 % | **25-35 %** |
| Synthetic (S) | 15-20 % | 5-10 % | **≤ 5 %** |
| Electricity demand that is measured energy | about 95 % (GB) | about 95 % (part Irish) | **about 95 %, Irish-fitted** |

Ceiling: about 60-70 % real. The people stay synthetic for privacy, and room physics and network flows in unmetered homes stay computed.

---

## 4. Governance

- **CSO:** every RMF used under ROSA; named researchers appointed Officers of Statistics; all outputs (including fitted parameters and any published synthetic data) submitted for CSO output checking before release.
- **ISSDA:** CER, TUS and HBS under the ISSDA licence; written answer on releasing synthetic data fitted to CER.
- **Consented homes:** UCC ethics approval, GDPR data-protection impact assessment, consent covering research and synthetic-data fitting, storage on UCC/Tyndall infrastructure only.
- **ESB Networks:** data-sharing agreement; aggregate use only.
- **Rule L7 continues:** Baile Nua is never presented as Cobh, a GB town or any real place.

---

## 5. Phases (indicative)

| Phase | Content | Depends on | Duration |
|---|---|---|---|
| A | Applications: ROSA (RMFs), ethics for consented homes, ESB Networks request | RMF contact at UCC | 4-12 weeks (approval-bound) |
| B | BER Energy fit (G1) | CSO access | 2-3 weeks |
| C | NTS, POWSCCAR, PWLB, SILC_ENERGY behaviour fits (G2) | CSO access | 3-4 weeks |
| D | Living town from CLD and Vital Statistics (G4) | CSO access | 2-3 weeks |
| E | Consented homes recruitment and integration (G3) | ethics, recruitment | 2-3 months, in parallel |
| F | Validation (held-out Irish homes, SCADA, blind test) and release with CSO output checking | B-E | 3-4 weeks |

Runs reuse the v2 parallel-year runner (about 32-34 h on the current instance).

---

## 6. Decisions for Brian

1. Approve v3 scope and the CSO RMF priority list.
2. Submit one ROSA application covering BER Energy, COP BER, NTS, POWSCCAR, SILC_ENERGY, CLD and PWLB (move POWSCCAR from v2.1).
3. Decide whether to recruit consented Cork homes (ethics and GDPR effort) and the target number.
4. Pursue the ESB Networks SCADA agreement for Cobh.
5. Confirm use of the NILM dataset and O-CEI pilot data.
