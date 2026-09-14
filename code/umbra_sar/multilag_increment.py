"""Coefficient-only multi-lag complex-increment diagnostics (Block15J).

The functions intentionally make no claim that pairs, lag classes, or Fourier
bins are independent Monte-Carlo observations.  A complete synthetic sequence
is the sole statistical unit.
"""
from __future__ import annotations

import numpy as np


def lag_pairs(times, edges, min_pairs=3):
    """Return fixed, disjoint time-lag classes for strictly increasing times."""
    t = np.asarray(times, float)
    e = np.asarray(edges, float)
    if t.ndim != 1 or len(t) < 3 or np.any(~np.isfinite(t)) or np.any(np.diff(t) <= 0):
        raise ValueError("times must be finite, strictly increasing and have >=3 entries")
    if e.ndim != 1 or len(e) < 2 or np.any(np.diff(e) <= 0) or e[0] < 0:
        raise ValueError("edges must be increasing non-negative values")
    out = []
    for lo, hi in zip(e[:-1], e[1:]):
        aa, bb = np.where((t[None, :] - t[:, None] >= lo) &
                          (t[None, :] - t[:, None] < hi) &
                          (np.arange(len(t))[None, :] > np.arange(len(t))[:, None]))
        if len(aa) < min_pairs:
            out.append(None)
        else:
            out.append((aa, bb))
    return out


def increment_structure(z, times, edges, weights=None, min_pairs=3, epsilon=1e-12):
    """Mean |z_b-z_a|^2 by predeclared lag class, energy-normalised.

    `z` is time by fixed spectral support.  Support weights are deterministic
    weights, normalised once; each pair in a class has equal weight.  The
    returned class values are descriptive aggregates, not independent samples.
    """
    x = np.asarray(z, complex)
    if x.ndim == 1:
        x = x[:, None]
    if x.ndim != 2 or x.shape[0] != len(times) or not np.all(np.isfinite(x)):
        raise ValueError("z must be finite time-by-support coefficients")
    if weights is None:
        w = np.full(x.shape[1], 1 / x.shape[1])
    else:
        w = np.asarray(weights, float)
        if w.shape != (x.shape[1],) or np.any(w < 0) or not np.isfinite(w).all() or w.sum() <= 0:
            raise ValueError("weights must be finite non-negative support weights")
        w = w / w.sum()
    denom = float(np.median(np.sum(w[None, :] * abs(x)**2, axis=1)))
    if not np.isfinite(denom) or denom <= epsilon:
        return dict(valid=False, reason="near_zero_energy", denominator=denom,
                    values=[None] * (len(edges) - 1), pair_counts=[0] * (len(edges) - 1), pairs=[])
    classes = lag_pairs(times, edges, min_pairs=min_pairs)
    values, counts, pairs = [], [], []
    for cl in classes:
        if cl is None:
            values.append(None); counts.append(0); pairs.append(None); continue
        a, b = cl
        energy = np.sum(w[None, :] * abs(x[b] - x[a])**2, axis=1)
        values.append(float(np.mean(energy) / denom)); counts.append(int(len(a))); pairs.append((a, b))
    return dict(valid=all(v is not None for v in values), reason=None, denominator=denom,
                values=values, pair_counts=counts, pairs=pairs)


def primary_score(structure):
    """Predeclared log late/early increment-energy ratio; no fitted truth."""
    values = structure["values"]
    if not structure["valid"] or values[0] is None or values[-1] is None or values[0] <= 0 or values[-1] <= 0:
        return None
    return float(np.log(values[-1] / values[0]))


def calibration_threshold(a_scores, quantile=.05):
    """Conservative order-statistic threshold fixed from calibration A only."""
    x = np.asarray(a_scores, float)
    if x.ndim != 1 or len(x) < 1 or not np.all(np.isfinite(x)) or not 0 < quantile < 1:
        raise ValueError("finite calibration A scores and a proper quantile are required")
    return float(np.quantile(x, quantile, method="higher"))


def b_decision(score, threshold):
    """One-sided B detector; non-detections are abstentions, never A labels."""
    return bool(score is not None and np.isfinite(score) and score <= threshold)


def sinusoid_increment_energy(amplitude, slope, delta_t):
    """Exact |a exp(i s t_b)-a exp(i s t_a)|^2 for a complex sinusoid."""
    return 4 * abs(amplitude)**2 * np.sin(0.5 * slope * np.asarray(delta_t))**2


def observed_constant_offset_identity(z, offset):
    """Maximum absolute difference of increments after an observed constant offset."""
    x = np.asarray(z, complex)
    return float(np.max(abs(np.diff(x + offset, axis=0) - np.diff(x, axis=0))))
