"""Cookie Cats gate experiment: full analysis.

Run from the repository root:  python -m abtest.analysis
Writes reports/results.json and reports/figures/.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from abtest.stats import (
    bootstrap_mean_diff, holm, mde_two_proportions, peeking_false_positive_rate,
    prob_b_better, sample_size_two_proportions, srm_test, two_proportion_test,
)

DATA = Path("data/cookie_cats.csv")
REPORTS = Path("reports")
FIGURES = REPORTS / "figures"
CONTROL, TREATMENT = "gate_30", "gate_40"


def rate_test(df: pd.DataFrame, metric: str) -> dict:
    a, b = df[df.version == CONTROL][metric], df[df.version == TREATMENT][metric]
    return two_proportion_test(int(a.sum()), len(a), int(b.sum()), len(b))


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(DATA)
    out: dict = {}

    # 1. Integrity checks before looking at any outcome
    n = df.version.value_counts()
    out["players"] = int(len(df))
    out["unique_userids"] = bool(df.userid.is_unique)
    out["srm_all"] = srm_test(int(n[CONTROL]), int(n[TREATMENT]))
    played = df[df.sum_gamerounds > 0].version.value_counts()
    never = df[df.sum_gamerounds == 0].version.value_counts()
    out["srm_played_at_least_once"] = srm_test(int(played[CONTROL]), int(played[TREATMENT]))
    out["srm_never_played"] = srm_test(int(never[CONTROL]), int(never[TREATMENT]))

    # 2. What the sample could detect
    n_arm = int(n.min())
    base7 = df[df.version == CONTROL].retention_7.mean()
    base1 = df[df.version == CONTROL].retention_1.mean()
    out["power"] = {
        "n_per_arm": n_arm,
        "mde_retention_7": mde_two_proportions(base7, n_arm),
        "mde_retention_1": mde_two_proportions(base1, n_arm),
        "n_needed_retention_1_for_observed_drop": sample_size_two_proportions(base1, 0.006),
    }

    # 3. Results: retention_7 is the decision metric, the others are secondary
    r7, r1 = rate_test(df, "retention_7"), rate_test(df, "retention_1")
    a_rounds = df[df.version == CONTROL].sum_gamerounds.to_numpy()
    b_rounds = df[df.version == TREATMENT].sum_gamerounds.to_numpy()
    outlier = int(df.sum_gamerounds.max())
    a_trim = a_rounds[a_rounds < outlier]
    rounds = {
        "mean_control": float(a_rounds.mean()), "mean_treatment": float(b_rounds.mean()),
        "median_control": float(np.median(a_rounds)), "median_treatment": float(np.median(b_rounds)),
        "outlier_removed": outlier,
        "mean_diff_without_outlier": bootstrap_mean_diff(a_trim, b_rounds),
        "mann_whitney_p": float(stats.mannwhitneyu(a_rounds, b_rounds).pvalue),
    }
    out["retention_7"], out["retention_1"], out["game_rounds"] = r7, r1, rounds
    out["holm"] = holm({"retention_7": r7["p_value"], "retention_1": r1["p_value"],
                        "game_rounds": rounds["mann_whitney_p"]})
    t = df[df.version == TREATMENT]
    c = df[df.version == CONTROL]
    out["prob_gate40_better_retention_7"] = prob_b_better(
        int(c.retention_7.sum()), len(c), int(t.retention_7.sum()), len(t))

    # 4. Does the conclusion survive the sample ratio mismatch? Worst case:
    # every surplus gate_40 player was a non-returner who should not be there.
    surplus = int(n[TREATMENT] - n.sum() / 2)
    worst = two_proportion_test(int(c.retention_7.sum()), len(c),
                                int(t.retention_7.sum()), len(t) - surplus)
    # Opposite extreme: surplus players were all returners.
    best = two_proportion_test(int(c.retention_7.sum()), len(c),
                               int(t.retention_7.sum()) - surplus, len(t) - surplus)
    out["srm_sensitivity"] = {"surplus_gate_40": surplus,
                              "surplus_all_non_returners": worst,
                              "surplus_all_returners": best}

    # 5. Why the stopping rule matters: A/A tests with repeated looks
    looks = [1, 2, 5, 10, 20]
    out["peeking_false_positive_rate"] = {
        k: peeking_false_positive_rate(base7, n_arm, k, sims=1000, seed=k) for k in looks}

    (REPORTS / "results.json").write_text(json.dumps(out, indent=2, default=float))

    # Figures
    fig, ax = plt.subplots(figsize=(6.5, 2.8))
    rows = [("1-day retention", r1), ("7-day retention\n(decision metric)", r7)]
    for i, (label, r) in enumerate(rows):
        ax.errorbar(r["diff"] * 100, i, xerr=[[(r["diff"] - r["ci_low"]) * 100], [(r["ci_high"] - r["diff"]) * 100]],
                    fmt="o", color="#0B6E4F", capsize=5, lw=2)
        ax.text(max(r["ci_high"], 0) * 100 + 0.08, i, f"{r['diff'] * 100:+.2f} pts, p = {r['p_value']:.3f}",
                va="center", fontsize=9)
    ax.axvline(0, color="grey", lw=1, ls="--")
    ax.set_yticks(range(len(rows)), [r[0] for r in rows])
    ax.set(xlabel="Gate at 40 minus gate at 30 (percentage points, 95% CI)", xlim=(-1.6, 0.9), ylim=(-0.6, 1.6),
           title="Moving the gate to level 40 lowered retention")
    fig.tight_layout(); fig.savefig(FIGURES / "effects.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    rates = [out["peeking_false_positive_rate"][k] * 100 for k in looks]
    ax.bar([str(k) for k in looks], rates, color="#C0392B")
    ax.axhline(5, color="grey", ls="--", lw=1)
    ax.text(-0.45, 5.6, "5% promised", ha="left", fontsize=9, color="grey")
    for x, v in enumerate(rates):
        ax.text(x, v + 0.4, f"{v:.1f}%", ha="center", fontsize=9)
    ax.set(xlabel="Times the result is checked before stopping", ylabel="False positives, %", ylim=(0, 30),
           title="A/A simulation: checking early inflates false positives")
    fig.tight_layout(); fig.savefig(FIGURES / "peeking.png", dpi=150); plt.close(fig)

    print(json.dumps(out, indent=2, default=float))


if __name__ == "__main__":
    main()
