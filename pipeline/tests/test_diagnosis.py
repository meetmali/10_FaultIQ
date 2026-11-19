from __future__ import annotations

import numpy as np
import polars as pl

from faultiq.detection import detectors as d
from faultiq.detection.windows import MIN_MINUTES, add_minute_context, window_table
from faultiq.diagnosis.classify import INCONCLUSIVE, MIN_NAMED, Classifier, decide, tune_cutoff
from faultiq.diagnosis.evaluate import answers, calibration_error, macro_f1
from faultiq.diagnosis.experiment import NOT_DIAGNOSABLE, _crossfit, end_to_end
from faultiq.diagnosis.features import (
    NORMAL,
    feature_columns,
    is_diagnosable,
    window_features,
)
from tests.test_detection import LABEL_FREE, minutes, normal_frame

SIM_CFG = {
    "basic": {"inputs": ["oat", "rat", "comp_stage"], "targets": ["sat"]},
    "all": {"inputs": ["oat", "rat", "comp_stage"], "targets": ["sat"]},
}

# ------------------------------------------------------------ features


def test_residuals_keep_their_sign_and_abstain_on_new_weather() -> None:
    model = d.NormalModel(["oat", "rat", "comp_stage"], ["sat"]).fit(normal_frame())
    probe = minutes(3, oat=[20.0, 20.0, 45.0], rat=23.0, comp_stage=1.0, sat=[19.0, 9.0, 19.0])
    r = model.residuals(probe)["resid:sat"]
    assert r[0] > 10  # 5 K warmer than expected: positive
    assert r[1] < -10  # 5 K colder: negative, so a diagnoser can tell the two apart
    assert r[2] is None  # outside the training envelope


def test_features_use_only_diagnosable_minutes() -> None:
    """Compressor-off minutes say nothing about refrigerant faults, so they must not dilute."""
    n = 60
    on = [True] * 40 + [False] * 20
    df = minutes(
        n, compressor_on=on, oat=20.0, rat=23.0, comp_stage=1.0,
        sat=[14.0] * 40 + [30.0] * 20, superheat=[5.0] * 40 + [50.0] * 20,
    )  # fmt: skip
    df = add_minute_context(df, LABEL_FREE)
    model = d.NormalModel(["oat", "rat", "comp_stage"], ["sat"]).fit(normal_frame())
    w = window_features(df, "simulated", {"basic": model, "all": model})
    assert w["n_diagnosable"][0] == 40
    assert w["med:superheat"][0] == 5.0  # the 20 compressor-off minutes are ignored
    assert MIN_MINUTES <= 40
    assert w.select(is_diagnosable())[0, 0]


def test_too_few_minutes_give_a_missing_feature_not_a_noisy_one() -> None:
    df = minutes(60, steady=[True] * 5 + [False] * 55, superheat=5.0, sat=14.0)
    df = add_minute_context(df, LABEL_FREE)
    model = d.NormalModel(["oat"], ["sat"])  # unfitted: no residual columns
    w = window_features(df, "simulated", {"basic": model, "all": model})
    assert w["med:superheat"][0] is None
    assert not w.select(is_diagnosable())[0, 0]


def test_features_leave_out_operating_conditions() -> None:
    """Faulty hours are selected by condition (e.g. outdoor-air band), so conditions would leak."""
    for ds in ("simulated", "experimental"):
        for ps in ("basic", "all"):
            cols = feature_columns(ds, ps)
            assert not {"med:oat", "med:rat", "med:occupied", "med:comp_stage"} & set(cols)
    assert set(feature_columns("experimental", "basic")) < set(
        feature_columns("experimental", "all")
    )


def test_crossfit_scores_normal_hours_with_a_model_that_never_saw_them() -> None:
    """One half runs 1 K warm. A model fitted on both halves absorbs half of that offset; the
    out-of-fold model for that half was fitted on the other half only, so it sees all of it."""
    frame = add_minute_context(normal_frame(n=2400), LABEL_FREE)
    warm = pl.int_range(pl.len()) >= 1200
    frame = frame.with_columns(pl.when(warm).then(pl.col("sat") + 1.0).otherwise(pl.col("sat")))
    halves = [frame[:1200], frame[1200:]]
    out = _crossfit(halves, "simulated", SIM_CFG, None).sort("window_start")
    assert out.height == window_table(frame).height
    both = d.NormalModel(["oat", "rat", "comp_stage"], ["sat"]).fit(frame)
    in_w = window_features(frame, "simulated", {"basic": both, "all": both}).sort("window_start")
    late = out["window_start"] >= frame["window_start"][1200]
    oof = out.filter(late)["resid:sat"].median()
    in_sample = in_w.filter(late)["resid:sat"].median()
    assert oof is not None and in_sample is not None
    assert float(oof) > float(in_sample) + 1  # type: ignore[arg-type]


# ------------------------------------------------------------ classifier and cut-off


def _separable(n: int = 300, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    y = np.array([NORMAL, "a", "b"])[rng.integers(0, 3, n)]
    x = np.column_stack(
        [
            np.where(y == "a", 3.0, 0.0) + rng.normal(0, 0.3, n),
            np.where(y == "b", -3.0, 0.0) + rng.normal(0, 0.3, n),
            rng.normal(0, 1, n),  # noise
        ]
    )
    x[::17, 2] = np.nan  # missing values must not break either model
    return x, y


def test_both_candidates_learn_and_explain_with_the_right_feature() -> None:
    x, y = _separable()
    cols = ["resid:a_signal", "resid:b_signal", "noise"]
    for fam in ("logistic", "lightgbm"):
        clf = Classifier(fam, cols).fit(x, y)
        p = clf.proba(x)
        assert p.shape == (len(y), 3)
        assert (clf.classes[p.argmax(axis=1)] == y).mean() > 0.95
        tops = np.array(clf.top_feature(x, p))
        assert (tops[y == "a"] == "resid:a_signal").mean() > 0.9
        assert (tops[y == "b"] == "resid:b_signal").mean() > 0.9


def test_cutoff_is_the_lowest_confidence_that_meets_the_target() -> None:
    classes = np.array([NORMAL, "a"])
    conf = np.linspace(0.5, 1.0, 100)
    proba = np.column_stack([1 - conf, conf])  # always predicts "a"
    truth = np.where(conf >= 0.8, "a", NORMAL)  # right only when confident
    t = tune_cutoff(proba, truth, classes, target=0.9)
    kept = conf >= t
    assert (truth[kept] == "a").mean() >= 0.9
    assert t < 0.8  # lowest that works, so some wrong answers are tolerated inside the 10%
    assert kept.sum() >= MIN_NAMED


def test_cutoff_never_names_a_fault_when_the_target_is_out_of_reach() -> None:
    classes = np.array([NORMAL, "a"])
    proba = np.column_stack([np.full(50, 0.1), np.full(50, 0.9)])
    truth = np.array([NORMAL] * 50)
    t = tune_cutoff(proba, truth, classes)
    assert t == float("inf")
    assert (decide(proba, classes, t) == INCONCLUSIVE).all()


def test_decide_says_inconclusive_below_the_cutoff() -> None:
    classes = np.array([NORMAL, "a"])
    proba = np.array([[0.2, 0.8], [0.45, 0.55], [0.9, 0.1]])
    assert decide(proba, classes, 0.7).tolist() == ["a", INCONCLUSIVE, NORMAL]


# ------------------------------------------------------------ metrics


def test_answers_split_what_the_user_sees() -> None:
    truth = np.array(["a", "a", "a", "a", NORMAL, NORMAL])
    answer = np.array(["a", "b", NORMAL, INCONCLUSIVE, NORMAL, "a"])
    out = answers(truth, answer)
    assert out["answered_share"] == round(5 / 6, 4)
    assert out["named_fault_precision"] == round(1 / 3, 4)  # a, b, a named; only the first right
    assert out["faulty_windows"] == {
        "correct_fault": 0.25, "wrong_fault": 0.25, "said_no_fault": 0.25, "inconclusive": 0.25,
    }  # fmt: skip
    assert out["normal_windows"]["named_a_fault"] == 0.5


def test_macro_f1_weighs_rare_classes_equally() -> None:
    truth = np.array(["a"] * 98 + ["b"] * 2)
    pred = np.array(["a"] * 100)
    assert macro_f1(truth, pred, ["a", "b"]) < 0.51  # 99% accurate, but class b is never found


def test_calibration_error_is_zero_when_confidence_matches_accuracy() -> None:
    classes = np.array(["a", "b"])
    proba = np.tile([0.8, 0.2], (10, 1))
    truth = np.array(["a"] * 8 + ["b"] * 2)
    assert calibration_error(proba, truth, classes) == 0.0


def test_end_to_end_outcomes() -> None:
    scored = pl.DataFrame(
        {
            "alarm": [True, True, True, True, True, False],
            "is_fault": [True, True, True, False, False, True],
            "fault": ["a", "a", "a", NORMAL, NORMAL, "a"],
            "answer": ["a", "b", NOT_DIAGNOSABLE, NORMAL, "a", "a"],
        }
    )
    out = end_to_end(scored)
    assert out["faulty_alarms"]["windows"] == 3
    assert out["faulty_alarms"]["correct_fault"] == round(1 / 3, 4)
    assert out["faulty_alarms"][NOT_DIAGNOSABLE] == round(1 / 3, 4)
    assert out["false_alarms"] == {"windows": 2, "named_a_fault": 0.5, "said_no_fault": 0.5}
