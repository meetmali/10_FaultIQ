# Dataset card: LBNL FDD Data Sets, Rooftop Unit

> **Status: verified against the downloaded files on 2026-11-18.** The documentation comes from the LBNL
> inventory PDF (*LBNL Fault Detection and Diagnostics Data Sets: Roof Top Unit*, 1 September 2022). Where
> the files disagree with it, the files win. See
> [Verified against the files](#verified-against-the-files). Reproduce the profile with
> `scripts/inspect_dataset.py`.

## Provenance

| Item | Value |
|---|---|
| Publisher | Lawrence Berkeley National Laboratory (LBNL) |
| Contributors | LBNL, Oak Ridge National Laboratory (ORNL), National Renewable Energy Laboratory (NREL), University of Connecticut |
| Funding | U.S. Department of Energy, Building Technologies Office |
| Web page | https://faultdetection.lbl.gov/dataset/rtu/ |
| DOI | https://dx.doi.org/10.25984/1881324 |
| Required citation | Lawrence Berkeley National Laboratory, LBNL FDD Data Sets. DOI: https://dx.doi.org/10.25984/1881324 |
| Licence | Not stated on the web page or in the inventory. **We treat it as: attribution required, no redistribution assumed.** |
| Access | Free, after a registration form (name, organisation, email, intended use) |
| Download | "All three RTU data set files" ZIP, about 293 MB (0.98 GB unpacked, per the web page) |

**Consequences for this repo:** the raw files are never committed (`data/raw/` is git-ignored), the
citation appears in the README and in any published results, and `data/sample/` contains only
synthetic data we generate ourselves.

## The three datasets

| | Simulated (S) | Experimental (E) | Field (F) |
|---|---|---|---|
| Source | NREL, Modelica + EnergyPlus co-simulation | ORNL Flexible Research Platform, Oak Ridge TN | UConn, two commercial sites in Connecticut |
| Equipment | 5-ton RTU (60,000 Btu/h), two-stage scroll compressor, R410A, multi-speed fan | Trane YCD150 12.5-ton RTU serving a 10-zone VAV system with electric reheat | 7.5-ton RTU (restaurant) and 10-ton RTU (distribution centre) |
| Building / climate | Single-zone 5,500 ft² small office, San Francisco TMY3, ASHRAE zone 3C (marine) | 3,200 ft² two-storey office emulator, zone 4A (mixed humid) | Real buildings, Milford CT and Colchester CT |
| Period | 100 days per scenario (20 July to 28 October, simulated year) | 1 day per fault case, in four seasons (Fall 2020 to Winter 2022) | About 1 to 5 months per case (2020 to 2021) |
| Sampling | 1 minute | 1 minute | 1 minute |
| Data points | 24 | 56 | 25 |
| Units | °F, cfm, Pa, W, %RH | °F, ACFM, W, SCFM, %RH, 0 to 1 | °C, CFM, bar, W, %RH |
| Fault files | 24 | 48 (12 cases × 4 seasons) | 2 |
| Fault-free files | 1 (`RTU_sim_baseline.csv`) | 4 (`ERTU_*.csv`, one per season) | 2 |
| Labels | Per file (file name = fault and intensity) | Per file | Per file |
| Economizer? | **No** (fixed ventilation of about 180 cfm) | Yes: OA and RA dampers, economizer setpoint 50 °F | Mixed air measured; economizer not described |

The web page says the simulated ZIP holds "74 .csv files". The download actually contains **81 CSV
files** (25 simulated, 52 experimental, 4 field), matching the inventory PDF. The folders are
`Simulated RTU/`, `ORNL_RTU/` and `Field RTU/`, plus the PDF and two Brick `.ttl` files.

## Fault scenarios

### Simulated: refrigerant-side faults, applied continuously for all 100 days

| Fault | Intensities | How it was imposed |
|---|---|---|
| Refrigerant overcharge | 10%, 15%, 20% | Lower refrigerant enthalpy |
| Refrigerant undercharge | 10%, 15%, 20% | Higher refrigerant enthalpy |
| Condenser fouling | 10% to 50% airflow reduction (5 levels) | Reduced condenser fan mass flow |
| Evaporator fouling | 10% to 50% airflow reduction (5 levels) | Reduced evaporator fan mass flow |
| Liquid-line restriction | 1, 4, 8, 10 bar pressure drop | Pressure drop after the condenser outlet |
| Suction-line restriction | 1, 3, 6, 9 bar pressure drop | Pressure drop after the evaporator outlet |

### Experimental: economizer and sensor faults, one day each, in four seasons

| Fault | Intensities (from file names) | Notes |
|---|---|---|
| Supply air temperature sensor bias | +4, +2, −2, −4 °C | The recorded `RTU_SA_TEMP` **is the biased value** |
| Incorrect economizer setpoint | +4, +2, −2, −4 °C relative to the correct 10 °C | The PDF table lists absolute setpoints 6, 8, 12, 14 °C |
| OA damper stuck | 5%, 10%, 50%, 100% open | Imposed through the control signal |

### Field: one real fault per site

| Site | Fault | Period |
|---|---|---|
| Milford CT (restaurant) | Compressor staging fault: stage 2 never engages | 9 June to 8 August 2021, plus unfaulted 10 August to 29 September 2021 |
| Colchester CT (distribution centre) | 40% undercharge on circuit B | June 2020, plus unfaulted summer 2020 and 2021 |

## Known limitations and what they mean for FaultIQ

1. **The simulated set has no economizer or mixed-air points.** Economizer and damper faults
   (the most common real RTU faults, and the subject of Title 24 FDD) exist only in the
   experimental set, and there only as single days.
2. **Most simulated fault signals are not "basic" BAS points.** The inventory marks refrigerant
   pressures and temperatures, flows, humidity and power as *not* commonly available in a building
   automation system. A model that depends on them won't work on typical BAS exports. We must report
   results both with all points and with **basic points only** (SA, RA, OA and zone temperature,
   compressor stage, zone setpoint).
3. **Faults are labelled per file, but they are only observable some of the time.** A refrigerant fault
   only shows while the compressor runs (`RTU_STG_STA` > 0.1). Measured run time is about 80% of rows in
   most simulated files, so about 20% of every "faulty" file looks normal. Run time itself also changes
   with severity: 67% for a 10 bar liquid-line restriction and 100% for 6 and 9 bar suction-line
   restriction. In the experimental set, run time varies from 5% to 62% per day, and is low on several
   winter days. Rows are scored only inside an **observability mask** (defined in Phase 3), never
   blindly by file label.
4. **One file per fault intensity, and every simulated file shares the same weather and timestamps.**
   A random split leaks, and a model could learn the timestamp instead of the fault. The split
   strategy (hold out intensity levels, or contiguous time blocks with gaps) is decided in Phase 3,
   based on the EDA.
5. **Units differ between datasets:** °F, cfm and Pa (simulated), °F and ACFM (experimental), °C, CFM
   and bar (field). The loader converts to one internal unit system and records the original unit.
6. **Missing and invalid data** takes several forms (details below): the string `"NAN"`, rows where
   every sensor reads exactly 0, `inf` values, a dead humidity sensor and negative pressures. None of
   it may be silently dropped or imputed. The loader flags it and the validation report counts it.
7. **Simulation artefact:** the simulated compressor "off" state is a capacity fraction of 0.1, not 0.
   The inventory says the corresponding power was removed in post-processing.
8. **Sim-to-real gap:** the field set is the only real-building data, with just two fault cases. It's
   best used as a reality check, not for training.

## Verified against the files

Profiled on 2026-11-18 with `scripts/inspect_dataset.py` (all 81 files, about 10 seconds).

### All datasets

- Every file has a `Datetime` column in `YYYY-MM-DD HH:MM:SS` format, with **no time zone**. Timestamps
  are treated as local equipment time. Within each dataset, every file has the same column set.
- The documentation's column names match the files exactly. The column *order* differs (files are
  alphabetical).

### Simulated (25 files)

| Check | Result |
|---|---|
| Rows and period | 143,941 rows per file, 2018-07-20 01:00 to 2018-10-28 00:00. **Identical timestamps in every file**, with no gaps, duplicates or missing values |
| Pressure unit | Documented as Pa, but values run from 6.3 × 10⁶ to 4.4 × 10⁷. Read as **psia × 10⁵**, the median suction superheat while the compressor runs is **4.87 K** (interquartile range 4.77 to 5.00 K), matching the documented 5 K expansion-valve setpoint. Read as Pa, superheat would be −38 K, which is physically impossible. **The loader treats these columns as psia × 10⁵.** |
| Compressor stage | `RTU_STG_STA` is 1.0 (43% of rows), 0.67 (34%) or 0.1, meaning off (20%), plus about 1% transition values. "Off" is 0.1, not 0 |
| Airflow | `RTU_SA_FLOW` and `RTU_RA_FLOW` range from 735 to 2,941 cfm, not the documented 1,000, 1,400 and 2,000 cfm. Kept as recorded and flagged as unexplained |
| Outdoor airflow | Constant within each file (about 182 cfm, matching the documented 180 cfm) |
| Resolution | Values change at every minute, not on a 10-minute grid, so this is genuine 1-minute output |
| Zone vs return air | `ZA_TEMP` and `RTU_RA_TEMP` cover the same range but are not identical row by row |

### Experimental (52 files)

| Check | Result |
|---|---|
| Rows and period | Fault files: exactly 1,440 rows (one day). Fault-free `ERTU_*` files: 2,880 to 11,520 rows covering several separate days, with gaps of 12 to 14 days between them |
| Damper unit | `RTU_OA_DMPR_DM` and `RTU_RA_DMPR_DM` are **0 to 100 (%)**, not the documented 0 to 1. In stuck-damper files the occupied-hours value is constant at the stuck position (for example 50.0) |
| `"NAN"` strings | About 24% of `RTU_SA_TEMP`, `RTU_RA_TEMP`, `RTU_SA_FLOW` and `VAV_RM_SAT_*` values, in 45 of 52 files |
| All-zero dropouts | 26 rows where every temperature, including outdoor and room temperatures, reads exactly 0 °F. These are logging dropouts, not readings |
| Infinite values | `RTU_SA_FLOW` contains `inf` in 3 files (55 rows) |
| Blank rows | One row with empty values in 6 of the fall files |
| Suspicious value | `RTU_SA_TEMP` reaches −7.2 °F in `SA_temp_bias_-4_Winter_2022.csv` |
| Occupancy | `OCCU_MOD` = 1 on 62.5% of rows (07:00 to 22:00) |

### Field (4 files)

| Check | Result |
|---|---|
| Rows and period | 41,522 to 260,441 rows. `Site2_Unfaulted.csv` joins two summers with a 243-day gap |
| Gaps | 108 to 556 gaps longer than one minute per file, up to 20 hours outside the long seasonal gap |
| Dead sensor | `ZA_HUM` is stuck between −15.04 and −14.80 in every file. It must be excluded |
| Invalid pressure | `RTU_REFG_DISC_PRES_2` goes as low as −9.99 bar |
| Compressor power | Only one compressor power column (`RTU_COMP_WATT`, circuit 1) for two-circuit units |

## EDA findings

From [`eda-report.md`](eda-report.md), generated by `scripts/eda_report.py`. All simulated files share the
baseline's timestamps and weather, so each fault is compared with the baseline **minute by minute at
identical conditions**, using only minutes where the compressor runs in both.

### Simulated faults: what is visible, and with which points

| Fault | Signature (median, fault minus baseline) | Visible with basic BAS points only? |
|---|---|---|
| Evaporator fouling | SAT 1.0 to 7.3 °C colder, suction pressure 32 to 198 kPa lower, capacity down; scales with severity | **Yes** (SAT) |
| Suction-line restriction | SAT up to 7.5 °C warmer, compressor running 95 to 100% from 3 bar, capacity down up to 7.6 kW | **Yes**, from 3 bar |
| Liquid-line restriction | Small until 8 to 10 bar; at 10 bar superheat +8.4 K and run time drops to 67% | Only at 8 to 10 bar (zone temperature, run time) |
| Condenser fouling | Discharge pressure +35 to +358 kPa, discharge temperature up to +11 °C, compressor power +75 to +693 W | **No** (SAT moves 0.4 °C at most) |
| Refrigerant undercharge | Small: suction pressure +3 to +22 kPa, discharge pressure −3 to −33 kPa | **Barely** |
| Refrigerant overcharge | **Not monotonic with severity** (discharge pressure −99, +9, +3 kPa at 10, 15, 20%) | Only at 20% (zone temperature −1.6 °C, run time 62%) |

Implications:

1. **Results must be reported twice**, with all points and with basic points only. Condenser fouling and
   charge faults are mostly invisible to a typical BAS.
2. **Superheat barely moves** (the expansion valve holds it near 5 K) except for the 10 bar liquid-line
   restriction. Classic superheat-based charge rules won't work on this data.
3. **Simulated undercharge raises suction pressure**, the opposite of the usual field behaviour. The
   simulation imposed charge faults through an enthalpy shift, which is a sim-to-real risk worth
   checking against the field undercharge case.
4. **Overcharge severities aren't ordered.** Diagnosis may need to merge overcharge levels, or return
   "inconclusive" for them.

### Experimental faults: economizer and sensor evidence

- **Stuck OA damper** is visible through the temperature-based outdoor-air fraction
  (OAF = (MAT − RAT) / (OAT − RAT), used only where |OAT − RAT| ≥ 5 K): about 0.73 to 0.91 when stuck at
  100% and 0.28 to 0.57 at 50%, against 0.21 to 0.26 fault-free. Stuck at 5 or 10% is close to normal
  operation and noisy. In summer, OAT and RAT are too close for the OAF to be reliable.
- **Fault-free OAF (about 0.2) is higher than the 10% minimum damper command.** A damper's airflow isn't
  proportional to its command. Rules must compare against the fault-free behaviour, not the raw
  command.
- **Supply air temperature bias hides itself:** median SAT is about 13 °C in every bias file, because the
  controller holds the *biased reading* at its 55 °F setpoint and the real air temperature shifts
  instead. Detecting it needs a cross-check, such as the 10 `VAV_RM_SAT_*` discharge temperatures or
  MAT plus fan heat when the compressor is off. **Phase 2 must map the VAV columns**, which the loader
  currently lists as unmapped.
- **Economizer setpoint offsets** are inconsistent across seasons on daily medians, and need
  minute-level, condition-aware analysis in Phase 3.

## Intended use in FaultIQ

- **Simulated set:** primary development set for the pipeline, detection and diagnosis of
  refrigerant-side faults (the plan's original starting point).
- **Experimental set:** economizer and sensor-bias faults, and rule baselines (Guideline 36 and APAR
  style), because it has mixed air temperature and damper signals.
- **Field set:** held out as a sim-to-real sanity check.

Confirmed after the Phase 1 EDA in [ADR 0018](decisions/0018-dataset-roles-and-dual-point-reporting.md), which also requires
every result to be reported with all points and with basic BAS points only.
