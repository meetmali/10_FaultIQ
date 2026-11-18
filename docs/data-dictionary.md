# Data dictionary

> **Status: verified against the downloaded files on 2026-11-18.** Column names come from the LBNL
> inventory (tables S3, E1 and F3), and every name matches the CSV headers. Where the files contradict a
> documented unit or range, this dictionary follows the files and says so in **bold**. Profiling details
> are in the [dataset card](dataset-card.md#verified-against-the-files).

**Timestamp:** every file has a `Datetime` column, `YYYY-MM-DD HH:MM:SS`, no time zone, 1-minute steps
(gaps exist in the experimental fault-free and field files).

## Canonical sensor roles

The pipeline works with **canonical roles**, not source column names. Each dataset (and later each
user's BAS export, through the Phase 2 point-mapping step) maps its columns onto these roles.
Canonical units are SI. The original unit is kept in the per-file metadata.

| Role | Meaning | Canonical unit | Basic BAS point? |
|---|---|---|---|
| `oat` | Outdoor air temperature | °C | Yes |
| `rat` | Return air temperature | °C | Yes |
| `mat` | Mixed air temperature | °C | Yes |
| `sat` | Supply air temperature | °C | Yes |
| `zone_temp` | Zone (room) air temperature | °C | Yes |
| `zone_temp_sp` | Zone cooling setpoint (single-zone) | °C | Yes |
| `zone_heat_sp` / `zone_cool_sp` | Zone heating and cooling setpoints (multi-zone) | °C | Yes |
| `oa_damper_cmd` | Outdoor air damper command, 0 = closed, 1 = open | fraction | Yes |
| `ra_damper_cmd` | Return air damper command | fraction | Yes |
| `comp_stage` | Compressor stage or capacity signal | fraction | Yes |
| `occupied` | Occupied mode flag | 0/1 | Yes |
| `sa_flow`, `ra_flow`, `oa_flow` | Volumetric airflow | m³/s | No |
| `sa_rh`, `ra_rh`, `oa_rh`, `ma_rh`, `zone_rh` | Relative humidity | % | No |
| `refg_disc_temp`, `refg_suct_temp`, `refg_cond_temp` | Refrigerant line temperatures | °C | No |
| `refg_disc_pres`, `refg_suct_pres`, `refg_cond_pres` | Refrigerant pressures | kPa | No |
| `power_total`, `power_comp`, `power_fan` | Electrical power | W | No |
| `cap_sensible`, `cap_total` | Cooling capacity | W | No |
| `gas_flow` | Natural gas consumption rate | SCFM (kept as is) | No |

Multi-circuit units add a circuit suffix: `power_comp_1`, `refg_suct_pres_2` and so on. Air leaving the
condenser is `cond_leaving_air_temp` (°C).

Units are converted as: °F → °C `(F − 32) × 5/9`; cfm → m³/s `× 0.000471947`; psia × 10⁵ → kPa
`÷ 10⁵ × 6.894757`; bar → kPa `× 100`; damper % → fraction `÷ 100`.

Physically implausible values are set to null and counted in the load report, never silently
dropped. Plausible ranges (canonical units): air temperatures −40 to 80 °C, refrigerant temperatures
−40 to 150 °C, pressures 0 to 6,000 kPa, relative humidity 0 to 100%, airflow 0 to 10 m³/s, power 0 to
100,000 W, fractions 0 to 1.

## Simulated set (24 points, documented in table S3)

| Source column | Role | Source unit | Description |
|---|---|---|---|
| `RTU_SA_TEMP` | `sat` | °F | Supply air temperature |
| `RTU_SA_FLOW` | `sa_flow` | cfm | Supply air volumetric flow |
| `RTU_SA_HUM` | `sa_rh` | 1 to 100 | Supply air relative humidity |
| `RTU_RA_TEMP` | `rat` | °F | Return air temperature |
| `RTU_RA_FLOW` | `ra_flow` | cfm | Return air volumetric flow |
| `RTU_RA_HUM` | `ra_rh` | 1 to 100 | Return air relative humidity |
| `RTU_OA_TEMP` | `oat` | °F | Outdoor air temperature |
| `RTU_OA_FLOW` | `oa_flow` | cfm | Outdoor air volumetric flow (constant, about 180 cfm) |
| `RTU_OA_HUM` | `oa_rh` | 1 to 100 | Outdoor air relative humidity |
| `RTU_STG_STA` | `comp_stage` | 0 to 1 | Compressor status: 0 off, 0.67 stage 1, 1 stage 2 (see note) |
| `RTU_REFG_DISC_TEMP` | `refg_disc_temp` | °F | Discharge temperature |
| `RTU_REFG_COND_TEMP` | `refg_cond_temp` | °F | Condenser outlet temperature |
| `RTU_REFG_SUCT_TEMP` | `refg_suct_temp` | °F | Suction temperature |
| `RTU_REFG_DISC_PRES` | `refg_disc_pres` | **psia × 10⁵** (documented as Pa) | Discharge pressure |
| `RTU_REFG_COND_PRES` | `refg_cond_pres` | **psia × 10⁵** (documented as Pa) | Condenser outlet pressure |
| `RTU_REFG_SUCT_PRES` | `refg_suct_pres` | **psia × 10⁵** (documented as Pa) | Suction pressure |
| `RTU_TOT_WATT` | `power_total` | W | Total RTU power |
| `RTU_COMP_WATT` | `power_comp` | W | Compressor power |
| `RTU_SA_FAN_WATT` | `power_fan` | W | Supply fan power |
| `RTU_SEN_CAPA` | `cap_sensible` | W | Sensible cooling capacity |
| `RTU_TOT_CAPA` | `cap_total` | W | Total cooling capacity |
| `ZA_TEMP` | `zone_temp` | °F | Zone air temperature |
| `ZA_HUM` | `zone_rh` | 1 to 100 | Zone relative humidity |
| `ZA_TEMP_SPT` | `zone_temp_sp` | °F | Zone cooling setpoint (fixed 23 °C) |

Notes from the files:

- **`RTU_STG_STA` uses 0.1 for "off"**, not the documented 0. Values are 1.0, 0.67 or 0.1, plus about 1%
  transition values. "Compressor running" means `RTU_STG_STA > 0.1`.
- **Pressure unit:** values divided by 10⁵ are psia. This is confirmed by the suction superheat
  (median 4.87 K against the documented 5 K setpoint). Conversion to kPa: `value ÷ 10⁵ × 6.894757`.
- **Supply and return airflow range from 735 to 2,941 cfm**, not the documented 1,000, 1,400 and 2,000 cfm.
  Kept as recorded.

## Experimental set (56 points, documented in table E1)

| Source column | Role | Source unit | Description |
|---|---|---|---|
| `RTU_OA_DMPR_DM` | `oa_damper_cmd` | **0 to 100 %** (documented as 0 to 1) | OA damper control signal (minimum 10%) |
| `RTU_RA_DMPR_DM` | `ra_damper_cmd` | **0 to 100 %** (documented as 0 to 1) | RA damper control signal (OA + RA = 100) |
| `RTU_OA_TEMP` | `oat` | °F | Outdoor air temperature |
| `RTU_MA_TEMP` | `mat` | °F | Mixed air temperature |
| `RTU_SA_TEMP` | `sat` | °F | Supply air temperature (biased value in SA bias fault files) |
| `RTU_RA_TEMP` | `rat` | °F | Return air temperature |
| `RTU_SA_FLOW` | `sa_flow` | ACFM | Supply air flow |
| `RTU_TOT_WATT` | `power_total` | W | RTU power |
| `RTU_GAS_CSUM` | `gas_flow` | SCFM | Natural gas consumption |
| `TERM_RM_TEMP_HSPT` | `zone_heat_sp` | °F | Zone heating setpoint (shared by all rooms) |
| `TERM_RM_TEMP_CSPT` | `zone_cool_sp` | °F | Zone cooling setpoint (shared by all rooms) |
| `TERM_RM_TEMP_<room>` | `zone_temp` per room | °F | Room temperature, 10 rooms |
| `TERM_RM_HUMD_<room>` | `zone_rh` per room | % | Room relative humidity, 10 rooms |
| `HVAC_TOT_WATT` | (system power) | W | RTU plus VAV reheat power |
| `OCCU_MOD` | `occupied` | 0/1 | Occupied mode (07:00 to 22:00) |
| `RTU_COMP_WATT_1`, `RTU_COMP_WATT_2` | `power_comp` per compressor | W | Compressor power |
| `RTU_SA_FAN_WATT` | `power_fan` | W | Supply fan power |
| `VAV_RM_WATT_<room>` | (VAV power) | W | VAV box power, 10 rooms |
| `VAV_RM_SAT_<room>` | (VAV discharge temp) | °F | VAV box supply air temperature, 10 rooms |

Rooms: 102, 103, 104, 105, 106, 202, 203, 204, 205, 206.

Invalid values the loader must flag: the string `"NAN"`, **rows where every temperature reads exactly 0**
(26 logging dropouts), **`inf` in `RTU_SA_FLOW`** (3 files), and one blank row in 6 fall files.

## Field set (25 points, documented in table F3)

| Source column | Role | Source unit |
|---|---|---|
| `RTU_RA_TEMP` | `rat` | °C |
| `RTU_SA_FAN_WATT` | `power_fan` | W |
| `RTU_COMP_WATT` | `power_comp` (stage 1, circuit 1) | W |
| `RTU_TOT_WATT` | `power_total` | W |
| `RTU_SA_FLOW` | `sa_flow` | CFM |
| `RTU_MA_HUM`, `RTU_OA_HUM`, `RTU_RA_HUM`, `RTU_SA_HUM` | humidity roles | %RH |
| `ZA_HUM` | **excluded: dead sensor**, stuck near −15 in every file | %RH |
| `RTU_SA_TEMP` | `sat` | °C |
| `RTU_MA_TEMP` | `mat` | °C |
| `RTU_OA_TEMP` | `oat` | °C |
| `ZA_TEMP` | `zone_temp` | °C |
| `RTU_REFG_DISC_PRES_1`, `_2` | `refg_disc_pres` per circuit | bar |
| `RTU_REFG_SUCT_PRES_1`, `_2` | `refg_suct_pres` per circuit | bar |
| `RTU_LA_COND_TEMP` | (air leaving condenser) | °C |
| `RTU_REFG_COND_TEMP_1`, `_2` | `refg_cond_temp` per circuit | °C |
| `RTU_REFG_SUCT_TEMP_1`, `_2` | `refg_suct_temp` per circuit | °C |
| `RTU_REFG_DISC_TEMP_1`, `_2` | `refg_disc_temp` per circuit | °C |

## Labels

| Dataset | Label source | Example |
|---|---|---|
| Simulated | File name | `RTU_sim_condfouling30.csv` → condenser fouling, 30% |
| Experimental | File name with season suffix | `OA_damper_stuck_050_Fall_2020.csv` → OA damper stuck at 50%, fall |
| Field | File name | `Site2_Undercharged40.csv` → 40% undercharge |

The loader parses fault type, intensity and season from file names with explicit, tested patterns.
A file whose name matches no pattern is reported, not guessed.
