from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import polars as pl
import pytest

from faultiq.detection import detectors as d
from faultiq.detection.evaluate import auc, confusion, predict, tune_threshold
from faultiq.detection.windows import (
    MIN_MINUTES,
    SEASONS,
    WINDOW_KEYS,
    add_minute_context,
    observable_expr,
    season_fold,
    sim_split,
    window_table,
)


def minutes(n: int, start: str = "2018-08-01 00:00:00", **cols: object) -> pl.DataFrame:
    t0 = datetime.fromisoformat(start)
    data: dict[str, object] = {"timestamp": [t0 + timedelta(minutes=i) for i in range(n)]}
    defaults: dict[str, object] = {
        "steady": True, "compressor_on": True, "fan_on": True, "operating_mode": "cooling",
    }  # fmt: skip
    for k, v in {**defaults, **cols}.items():
        data[k] = v if isinstance(v, list) else [v] * n
    return pl.DataFrame(data).with_columns(pl.col("timestamp").cast(pl.Datetime("us")))


LABEL_FREE = {"source_name": "free.csv", "fault": "fault_free", "intensity": None, "season": None}


# ------------------------------------------------------------ observability and windows


def test_refrigerant_faults_are_observable_only_with_the_compressor_running() -> None:
    df = minutes(3, compressor_on=[True, False, True], steady=[True, True, False])
    obs = df.select(observable_expr("condenser_fouling", 30.0, set(df.columns))).to_series()
    assert obs.to_list() == [True, False, False]


def test_economizer_offset_is_observable_only_between_the_two_setpoints() -> None:
    df = minutes(4, oat=[5.0, 9.0, 11.0, 15.0])
    obs = df.select(
        observable_expr("economizer_setpoint_offset", -4.0, set(df.columns))
    ).to_series()
    assert obs.to_list() == [False, True, False, False]  # wrong setpoint 6 C, correct 10 C


def test_windows_are_hourly_and_need_enough_minutes() -> None:
    df = add_minute_context(minutes(90, steady=[True] * 60 + [False] * 30), LABEL_FREE)
    w = window_table(df)
    assert w.height == 2
    assert w["n_steady"].to_list() == [60, 0]
    assert w["evaluable"].to_list() == [True, False]
    assert w["mode"][0] == "cooling"
    assert MIN_MINUTES == 30


def test_simulated_split_blocks_have_gaps() -> None:
    days = [0, 59, 60, 61, 80, 81, 82, 99]
    ts = pl.Series([datetime(2018, 7, 20) + timedelta(days=x, hours=5) for x in days])
    split = pl.DataFrame({"t": ts}).select(sim_split(pl.col("t"))).to_series().to_list()
    assert split == ["train", "train", None, "val", "val", None, "test", "test"]


def test_every_season_is_tested_exactly_once_and_never_trained_on() -> None:
    tested = []
    for s in SEASONS:
        roles = season_fold(s)
        assert roles[s] == "test"
        assert sorted(roles.values()) == ["test", "train", "train", "val"]
        tested.append(s)
    assert sorted(tested) == sorted(SEASONS)


# ------------------------------------------------------------ detectors


def normal_frame(n: int = 2000, seed: int = 0) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    oat = rng.uniform(10, 30, n)
    return minutes(
        n,
        oat=list(oat),
        rat=list(23 + rng.normal(0, 0.2, n)),
        comp_stage=list(rng.choice([0.67, 1.0], n)),
        sat=list(12 + 0.1 * oat + rng.normal(0, 0.2, n)),
        sa_flow=list(rng.choice([1.0, 1.4], n)),  # few distinct values, like fan speeds
    )


def test_limit_rules_score_distance_outside_the_normal_range() -> None:
    rules = d.LimitRules(["sat"]).fit(normal_frame())
    probe = minutes(3, oat=[20.0, 20.0, 45.0], sat=[14.0, 40.0, 40.0])
    s = rules.score(probe).to_series()
    assert s[0] == 0.0  # inside the normal range
    assert s[1] > 1.0  # far above it
    assert s[2] is None  # outdoor air outside the training envelope: abstain


def test_economizer_rules() -> None:
    df = minutes(
        4,
        oat=[20.0, 20.0, 5.0, 5.0],
        oa_damper_cmd=[0.9, 0.1, 0.1, 0.9],
        compressor_on=[False, False, True, True],
    )
    s = d.EconomizerRules("basic").score(df)
    assert s["economizer_rules:economizing_when_should_not"].to_list() == [1.0, 0.0, None, None]
    assert s["economizer_rules:not_economizing_when_should"].to_list() == [None, None, 1.0, 0.0]


def test_normal_model_learns_normal_and_flags_shifts_but_not_new_weather() -> None:
    model = d.NormalModel(["oat", "rat", "comp_stage"], ["sat", "sa_flow"]).fit(normal_frame())
    assert (
        model.scales["sa_flow"] > 0.001
    )  # perfectly-fitted discrete target still has a real scale
    probe = minutes(
        3, oat=[20.0, 20.0, 45.0], rat=23.0, comp_stage=1.0, sat=[14.0, 19.0, 19.0], sa_flow=1.0
    )
    z = model.score(probe)["normal_model:sat"]
    assert z[0] < 3
    assert z[1] > 10  # 5 K above what the model expects
    assert z[2] is None  # 45 C outdoor air was never seen in training: abstain


def test_severe_fault_in_return_air_is_still_scored() -> None:
    model = d.NormalModel(["oat", "rat", "comp_stage"], ["sat"]).fit(normal_frame())
    probe = minutes(1, oat=20.0, rat=30.0, comp_stage=1.0, sat=25.0)  # zone far warmer than ever
    assert model.score(probe)["normal_model:sat"][0] is not None


def test_window_score_needs_enough_applicable_minutes_and_names_the_signal() -> None:
    df = add_minute_context(minutes(60), LABEL_FREE)
    scores = pl.DataFrame({"x:a": [1.0] * 60, "x:b": [3.0] * 5 + [None] * 55})
    w = d.window_scores(df, scores, WINDOW_KEYS)
    assert w["score"][0] == 1.0  # signal b had only 5 minutes, below MIN_APPLICABLE
    assert w["top_signal"][0] == "a"


# ------------------------------------------------------------ evaluation


def test_threshold_respects_false_alarm_budget_even_with_heavy_imbalance() -> None:
    # 24 faulty to 1 normal, like the simulated set: maximising F1 would alarm on everything.
    rng = np.random.default_rng(1)
    normal = rng.normal(0, 1, 100)
    faulty = rng.normal(0.5, 1, 2400)
    scores = pl.Series(np.concatenate([normal, faulty]))
    labels = pl.Series([False] * 100 + [True] * 2400)
    threshold, m = tune_threshold(scores, labels, max_fpr=0.05)
    assert m.fpr <= 0.05
    assert m.recall < 1.0
    assert threshold > float(np.quantile(normal, 0.9))


def test_unscored_windows_never_alarm() -> None:
    assert predict(pl.Series([None, 2.0, 0.5]), 1.0).to_list() == [False, True, False]


def test_confusion_and_auc() -> None:
    m = confusion(pl.Series([True, True, False, False]), pl.Series([True, False, True, False]))
    assert (m.tp, m.fn, m.fp, m.tn) == (1, 1, 1, 1)
    assert m.f1 == pytest.approx(0.5)
    assert auc(pl.Series([0.9, 0.8, 0.1, None]), pl.Series([True, True, False, False])) == 1.0
