# Processed data contract

What `python -m faultiq process-lbnl` and `python -m faultiq process` produce (pipeline version
0.2.0, [ADR 0020](decisions/0020-preprocessing-contract.md)). Phase 3 and later read only these files.

## Files

```text
data/processed/v<pipeline_version>/
├── manifest.json                 # every input: source hash, status, output, output hash, label
└── <dataset or run>/
    ├── <source>.parquet          # accepted files only
    └── <source>.report.json      # every file, accepted or quarantined
```

`data/processed/` is git-ignored. Rebuild it at any time; the same input always gives byte-identical
output.

## Columns in each Parquet file

| Column | Type | Meaning |
|---|---|---|
| `timestamp` | datetime | Grid time (snapped to the file's sampling interval) |
| *roles* | float | Every mapped sensor role in canonical SI units (see [data dictionary](data-dictionary.md)) |
| `qc_dropout` | bool | The source row was a logging dropout; its values are null |
| `segment` | int | Continuous stretch of data. A gap over 60 minutes starts a new segment |
| `observed` | bool | `false` for a grid step missing from the source. Its values are null, never filled |
| `fan_on` | bool | Supply flow above 0.05 m³/s, or fan power above 50 W |
| `compressor_on` | bool | `comp_stage` > 0.1, or any compressor circuit above 200 W |
| `heating_on` | bool | Gas flow above 0 (false when no heating signal exists) |
| `economizer_on` | bool | OA damper command above 15% (false when there is no damper) |
| `operating_mode` | enum | off, fan_only, economizer, cooling, economizer_cooling, heating, unknown |
| `mode_minutes` | float | Minutes since the mode last changed (restarts at each segment) |
| `steady` | bool | Mode unchanged for 10 minutes, and not off or unknown |

## Physics features

Added only when their input roles exist. Null where an input is missing or the physics is undefined.

| Feature | Formula | Needs | Basic points only? |
|---|---|---|---|
| `oaf_temp` | (mat − rat) / (oat − rat), only where abs(oat − rat) ≥ 5 K | mat, rat, oat | Yes |
| `oaf_flow` | oa_flow / sa_flow | oa_flow, sa_flow | No |
| `rat_minus_sat` | rat − sat | rat, sat | Yes |
| `mat_minus_sat` | mat − sat | mat, sat | Yes |
| `zone_temp_error` | zone_temp − zone_temp_sp | zone_temp, zone_temp_sp | Yes |
| `superheat` | suction temperature − R410A saturation temperature at suction pressure | refrigerant points | No |
| `subcooling` | saturation temperature at condenser pressure − condenser outlet temperature | refrigerant points | No |
| `condensing_approach` | saturation temperature at discharge pressure − oat | refrigerant points, oat | No |
| `comp_power_per_capacity` | power_comp / cap_total, where cap_total > 500 W | power, capacity | No |
| `sensible_heat_ratio` | cap_sensible / cap_total, where cap_total > 500 W | capacities | No |
| `vav_sat_min` | coldest VAV discharge temperature | vav_sat_* | No (needs VAV points) |
| `sat_minus_vav_sat_min` | sat − vav_sat_min | sat, vav_sat_* | No (needs VAV points) |

## What Phase 2 verified on the real data

- **Simulated baseline, steady cooling:** median superheat 4.9 K (the valve setpoint is 5 K), sensible heat
  ratio 0.86, outdoor-air fraction from flows 0.06.
- **The supply air sensor bias is recoverable.** On steady compressor-on minutes, `sat_minus_vav_sat_min`
  tracks the injected bias: −2 → −2.2, −4 → −4.0, +2 → +1.9, +4 → +4.0 / +3.5 °C, against about 0.0 °C on
  fault-free days. A bias that hides in its own trend shows clearly against the VAV discharge readings.
  Negative-bias days also have very few compressor-on minutes: a sensor reading too cold makes the
  controller cut cooling, which is a symptom in itself.
- **Field set:** the 243-day gap in `Site2_Unfaulted.csv` becomes a new segment rather than 350,000 empty
  rows. Only 872 genuinely missing minutes are inserted.
