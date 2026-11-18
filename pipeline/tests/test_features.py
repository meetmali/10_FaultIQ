from __future__ import annotations

import polars as pl
import pytest

from faultiq.features.physics import add_physics_features
from faultiq.features.refrigerant import saturation_temp_c


def test_outdoor_air_fraction_from_temperatures() -> None:
    df = pl.DataFrame({"oat": [0.0, 20.0], "rat": [20.0, 22.0], "mat": [15.0, 21.0]})
    out = add_physics_features(df)
    assert out["oaf_temp"][0] == pytest.approx(0.25)  # 5 K of a 20 K spread
    assert out["oaf_temp"][1] is None  # |OAT - RAT| = 2 K: too close to trust


def test_features_appear_only_when_inputs_exist() -> None:
    out = add_physics_features(pl.DataFrame({"sat": [13.0], "rat": [24.0]}))
    assert out["rat_minus_sat"][0] == pytest.approx(11.0)
    assert "oaf_temp" not in out.columns and "superheat" not in out.columns


def test_saturation_curve_points_and_nulls() -> None:
    s = (
        pl.DataFrame({"p": [1085.0, 1440.0, None]})
        .select(saturation_temp_c(pl.col("p")))
        .to_series()
    )
    assert s.to_list()[:2] == pytest.approx([10.0, 20.0])
    assert s[2] is None


def test_refrigerant_features() -> None:
    df = pl.DataFrame({
        "refg_suct_temp": [15.0], "refg_suct_pres": [1085.0],   # sat 10 C -> superheat 5 K
        "refg_cond_temp": [35.0], "refg_cond_pres": [2420.0],   # sat 40 C -> subcooling 5 K
        "refg_disc_pres": [2420.0], "oat": [30.0],             # approach 10 K
        "power_comp": [1000.0], "cap_total": [5000.0], "cap_sensible": [4000.0],
    })  # fmt: skip
    row = add_physics_features(df).row(0, named=True)
    assert row["superheat"] == pytest.approx(5.0)
    assert row["subcooling"] == pytest.approx(5.0)
    assert row["condensing_approach"] == pytest.approx(10.0)
    assert row["comp_power_per_capacity"] == pytest.approx(0.2)
    assert row["sensible_heat_ratio"] == pytest.approx(0.8)


def test_vav_cross_check_reveals_a_biased_supply_sensor() -> None:
    # The RTU reads 17 C but the coldest VAV discharge (no reheat) shows the air is really 13 C.
    df = pl.DataFrame({"sat": [17.0], "vav_sat_102": [13.0], "vav_sat_103": [19.5]})
    row = add_physics_features(df).row(0, named=True)
    assert row["vav_sat_min"] == pytest.approx(13.0)
    assert row["sat_minus_vav_sat_min"] == pytest.approx(4.0)
