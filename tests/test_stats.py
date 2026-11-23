import numpy as np
import pytest
from statsmodels.stats.proportion import proportions_ztest

from abtest.stats import (
    holm, mde_two_proportions, peeking_false_positive_rate, prob_b_better,
    sample_size_two_proportions, srm_test, two_proportion_test,
)


def test_z_test_matches_statsmodels():
    r = two_proportion_test(8502, 44700, 8279, 45489)
    z, p = proportions_ztest([8279, 8502], [45489, 44700])
    assert r["z"] == pytest.approx(z)
    assert r["p_value"] == pytest.approx(p)
    assert r["ci_low"] < r["diff"] < r["ci_high"]


def test_srm_flags_an_unbalanced_split_only():
    assert srm_test(5000, 5000)["p_value"] == pytest.approx(1.0)
    assert srm_test(44700, 45489)["p_value"] < 0.01


def test_sample_size_and_mde_agree():
    n = sample_size_two_proportions(0.19, 0.01)
    assert mde_two_proportions(0.19, n) == pytest.approx(0.01, rel=0.05)


def test_holm_is_never_less_strict_than_raw_p():
    out = holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert out["a"]["p_adjusted"] == pytest.approx(0.03)
    assert all(v["p_adjusted"] >= v["p_value"] for v in out.values())
    assert [out[k]["reject"] for k in "abc"] == [True, False, False]


def test_prob_b_better_is_symmetric():
    assert prob_b_better(100, 1000, 100, 1000) == pytest.approx(0.5, abs=0.01)


def test_single_look_aa_test_keeps_its_false_positive_rate():
    rate = peeking_false_positive_rate(0.2, 2000, looks=1, sims=2000, seed=1)
    assert rate == pytest.approx(0.05, abs=0.015)
    assert peeking_false_positive_rate(0.2, 2000, looks=10, sims=2000, seed=1) > rate
