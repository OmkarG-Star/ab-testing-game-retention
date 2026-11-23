"""Statistics for a two-arm A/B test on binary and skewed metrics."""

from __future__ import annotations

import numpy as np
from scipy import stats


def srm_test(n_a: int, n_b: int, expected_share_a: float = 0.5) -> dict:
    """Chi-square sample ratio mismatch test against the planned split."""
    total = n_a + n_b
    expected = [total * expected_share_a, total * (1 - expected_share_a)]
    chi2, p = stats.chisquare([n_a, n_b], expected)
    return {"n_a": n_a, "n_b": n_b, "share_a": n_a / total, "chi2": float(chi2), "p_value": float(p)}


def two_proportion_test(x_a: int, n_a: int, x_b: int, n_b: int, alpha: float = 0.05) -> dict:
    """Pooled z-test for p_b - p_a, with an unpooled Wald confidence interval."""
    p_a, p_b = x_a / n_a, x_b / n_b
    pooled = (x_a + x_b) / (n_a + n_b)
    se_pooled = np.sqrt(pooled * (1 - pooled) * (1 / n_a + 1 / n_b))
    z = (p_b - p_a) / se_pooled
    p_value = 2 * stats.norm.sf(abs(z))
    se = np.sqrt(p_a * (1 - p_a) / n_a + p_b * (1 - p_b) / n_b)
    crit = stats.norm.ppf(1 - alpha / 2)
    diff = p_b - p_a
    return {"rate_a": p_a, "rate_b": p_b, "diff": diff, "relative_lift": diff / p_a,
            "ci_low": diff - crit * se, "ci_high": diff + crit * se,
            "z": float(z), "p_value": float(p_value)}


def mde_two_proportions(baseline: float, n_per_arm: int, alpha=0.05, power=0.8) -> float:
    """Smallest absolute difference detectable with the given sample size."""
    z = stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)
    return float(z * np.sqrt(2 * baseline * (1 - baseline) / n_per_arm))


def sample_size_two_proportions(baseline: float, mde: float, alpha=0.05, power=0.8) -> int:
    """Players needed per arm to detect an absolute drop of `mde`."""
    p2 = baseline - mde
    z_a, z_b = stats.norm.ppf(1 - alpha / 2), stats.norm.ppf(power)
    p_bar = (baseline + p2) / 2
    num = (z_a * np.sqrt(2 * p_bar * (1 - p_bar)) + z_b * np.sqrt(baseline * (1 - baseline) + p2 * (1 - p2))) ** 2
    return int(np.ceil(num / mde ** 2))


def holm(p_values: dict[str, float], alpha: float = 0.05) -> dict[str, dict]:
    """Holm-Bonferroni: adjusted p-values and reject decisions."""
    names = sorted(p_values, key=p_values.get)
    m, running, out = len(names), 0.0, {}
    for i, name in enumerate(names):
        adj = min(1.0, max(running, (m - i) * p_values[name]))
        running = adj
        out[name] = {"p_value": p_values[name], "p_adjusted": adj, "reject": adj < alpha}
    return out


def bootstrap_mean_diff(a: np.ndarray, b: np.ndarray, n: int = 2000, seed: int = 0) -> dict:
    """Percentile bootstrap CI for mean(b) - mean(a)."""
    rng = np.random.default_rng(seed)
    a, b = np.asarray(a, float), np.asarray(b, float)
    diffs = np.empty(n)
    for i in range(n):
        diffs[i] = rng.choice(b, len(b)).mean() - rng.choice(a, len(a)).mean()
    return {"diff": float(b.mean() - a.mean()), "ci_low": float(np.percentile(diffs, 2.5)),
            "ci_high": float(np.percentile(diffs, 97.5))}


def prob_b_better(x_a, n_a, x_b, n_b, draws=200_000, seed=0) -> float:
    """P(rate_b > rate_a) under independent Beta(1, 1) priors."""
    rng = np.random.default_rng(seed)
    a = rng.beta(1 + x_a, 1 + n_a - x_a, draws)
    b = rng.beta(1 + x_b, 1 + n_b - x_b, draws)
    return float((b > a).mean())


def peeking_false_positive_rate(baseline: float, n_per_arm: int, looks: int,
                                sims: int = 2000, alpha: float = 0.05, seed: int = 0) -> float:
    """Share of A/A tests declared significant at any of `looks` equally spaced checks."""
    rng = np.random.default_rng(seed)
    checkpoints = np.linspace(n_per_arm / looks, n_per_arm, looks).astype(int)
    hits = 0
    for _ in range(sims):
        a = rng.random(n_per_arm) < baseline
        b = rng.random(n_per_arm) < baseline
        ca, cb = np.cumsum(a), np.cumsum(b)
        for k in checkpoints:
            if two_proportion_test(ca[k - 1], k, cb[k - 1], k, alpha)["p_value"] < alpha:
                hits += 1
                break
    return hits / sims
