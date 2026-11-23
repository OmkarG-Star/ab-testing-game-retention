"""A/B test calculator: check a finished test, or plan the sample size for a new one."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from abtest.stats import (  # noqa: E402
    mde_two_proportions, prob_b_better, sample_size_two_proportions, srm_test,
    two_proportion_test,
)

st.set_page_config(page_title="A/B Test Calculator", layout="wide")
st.title("A/B Test Calculator")
st.caption("For conversion-style metrics (did the user do X: yes or no). Opens with the "
           "Cookie Cats 7-day retention result; replace the numbers with your own test.")

check, plan = st.tabs(["Check a finished test", "Plan a new test"])

with check:
    left, right = st.columns([1, 1.3], gap="large")
    with left:
        st.subheader("Your numbers")
        a1, a2 = st.columns(2)
        n_a = a1.number_input("Users in A (control)", 1, 100_000_000, 44700)
        x_a = a2.number_input("Conversions in A", 0, 100_000_000, 8502)
        b1, b2 = st.columns(2)
        n_b = b1.number_input("Users in B (variant)", 1, 100_000_000, 45489)
        x_b = b2.number_input("Conversions in B", 0, 100_000_000, 8279)
        planned = st.slider("Planned share of traffic to A (%)", 1, 99, 50)
        conf = st.select_slider("Confidence level", [90, 95, 99], 95)
    alpha = 1 - conf / 100

    if x_a > n_a or x_b > n_b:
        right.error("Conversions can't be more than users.")
    else:
        srm = srm_test(int(n_a), int(n_b), planned / 100)
        res = two_proportion_test(int(x_a), int(n_a), int(x_b), int(n_b), alpha)
        p_better = prob_b_better(int(x_a), int(n_a), int(x_b), int(n_b), draws=100_000)
        with right:
            st.subheader("1. Was the traffic split as planned?")
            if srm["p_value"] < 0.01:
                st.error(f"Sample ratio mismatch: A got {srm['share_a']:.2%} of users, planned "
                         f"{planned}% (p = {srm['p_value']:.4f}). Find out why before trusting the "
                         "result; a bug in assignment or logging can bias everything below.")
            else:
                st.success(f"Split looks fine: A got {srm['share_a']:.2%} of users, planned "
                           f"{planned}% (p = {srm['p_value']:.3f}).")

            st.subheader("2. Result")
            m1, m2, m3 = st.columns(3)
            m1.metric("Rate in A", f"{res['rate_a']:.2%}")
            m2.metric("Rate in B", f"{res['rate_b']:.2%}",
                      f"{res['diff'] * 100:+.2f} pts ({res['relative_lift']:+.1%})")
            m3.metric("p-value", f"{res['p_value']:.4f}")
            st.markdown(f"**{conf}% confidence interval for B − A:** "
                        f"{res['ci_low'] * 100:+.2f} to {res['ci_high'] * 100:+.2f} percentage points  \n"
                        f"**Probability B is better than A** (Bayesian, flat prior): {p_better:.1%}")
            sig = res["p_value"] < alpha
            if sig and res["diff"] < 0:
                st.warning("B is significantly **worse** than A. Keep A.")
            elif sig:
                st.success("B is significantly **better** than A.")
            else:
                mde = mde_two_proportions(res["rate_a"], int(min(n_a, n_b)), alpha)
                st.info(f"No significant difference. With this many users the test could only "
                        f"reliably detect a change of about {mde * 100:.2f} points or more, so a "
                        "smaller real effect may have been missed.")
            st.caption("Valid only if you decided the sample size in advance and looked once at the "
                       "end. Checking repeatedly and stopping at the first significant result "
                       "inflates false positives: about 26% instead of 5% with 20 looks.")

with plan:
    left, right = st.columns([1, 1.3], gap="large")
    with left:
        st.subheader("Your test")
        base = st.number_input("Current conversion rate (%)", 0.1, 99.0, 19.0, step=0.5) / 100
        mde_pts = st.number_input("Smallest change worth detecting (percentage points)", 0.05, 50.0,
                                  1.0, step=0.1) / 100
        power = st.select_slider("Power (chance of detecting a real effect)", [70, 80, 90, 95], 80) / 100
        conf_p = st.select_slider("Confidence level ", [90, 95, 99], 95)
        daily = st.number_input("Users per day entering the test (both groups)", 1, 10_000_000, 5000)
    with right:
        if mde_pts >= base:
            st.error("The change must be smaller than the current rate.")
        else:
            n = sample_size_two_proportions(base, mde_pts, 1 - conf_p / 100, power)
            days = int(np.ceil(2 * n / daily))
            st.subheader("You need")
            c1, c2 = st.columns(2)
            c1.metric("Users per group", f"{n:,}")
            c2.metric("Days at your traffic", f"{days:,}")
            if days < 7:
                st.caption("Run at least a full week anyway, so weekday and weekend users are both included.")
            curve = pd.DataFrame({"Change (pts)": np.round(np.linspace(mde_pts / 2, mde_pts * 3, 25) * 100, 3)})
            curve["Users per group"] = [sample_size_two_proportions(base, d / 100, 1 - conf_p / 100, power)
                                        if d / 100 < base else np.nan for d in curve["Change (pts)"]]
            st.markdown("**Smaller effects need far more users**")
            st.line_chart(curve.set_index("Change (pts)"), color="#0B6E4F")
