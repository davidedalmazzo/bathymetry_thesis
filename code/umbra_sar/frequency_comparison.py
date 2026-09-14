"""Block15B: raw-bin estimators, descriptive diagnostics, no ocean inversion.

All cross spectra are secondary * conj(reference). Spatial averaging is ONLY
used for MSC. Shared-look pair residuals are not independent observations.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import convolve
from scipy.optimize import minimize_scalar


def local_msc(reference, secondary, size=3):
    """Complete finite square patches only; zero power -> 0, invalid flag.

    Borders are invalid (no periodic wrap or shortened patches). Return gamma^2
    and a support/power-valid mask; a valid low MSC is not a numerical failure.
    """
    a, b = np.asarray(reference, complex), np.asarray(secondary, complex)
    if a.shape != b.shape or a.ndim != 2 or size < 1 or size % 2 != 1:
        raise ValueError('Matching 2D arrays and positive odd patch size required')
    finite = np.isfinite(a) & np.isfinite(b)
    a, b = np.where(finite, a, 0), np.where(finite, b, 0)
    kernel = np.ones((size, size)) / size**2
    smooth = lambda x: convolve(x, kernel, mode='constant', cval=0)
    c = smooth(b * a.conj())
    denominator = smooth(abs(a)**2) * smooth(abs(b)**2)
    valid = (smooth(finite.astype(float)) > 1 - 1e-12) & (denominator > 0)
    valid &= np.isfinite(denominator) & np.isfinite(c)
    gamma2 = np.zeros(a.shape)
    np.divide(abs(c)**2, denominator, out=gamma2, where=valid)
    return np.clip(gamma2, 0, 1), valid


def _series(coefficients, times):
    z, t = np.asarray(coefficients, complex), np.asarray(times, float)
    if z.ndim != 1 or z.shape != t.shape or t.size < 3:
        raise ValueError('Matching 1D series with >=3 looks required')
    if not np.all(np.isfinite(t)) or np.any(np.diff(t) <= 0):
        raise ValueError('Times must be finite and strictly increasing')
    if not np.all(np.isfinite(z)) or np.any(abs(z) == 0):
        raise ValueError('Nonfinite or zero coefficient: phase undefined')
    return z, t


def reference_fit(coefficients, times, reference, max_step=0.8*np.pi):
    """Historical OLS with free intercept and unconditional unwrap diagnostic.

    The reported slope is retained even if the continuity guard fails; validity
    must be applied separately. Small wrapped increments are necessary, not a
    proof against a faster aliased signal.
    """
    z, t = _series(coefficients, times)
    wrapped = np.angle(z * np.conj(z[reference]))
    phase = np.unwrap(wrapped)
    tc = t - t.mean()
    slope = np.dot(tc, phase) / np.dot(tc, tc)
    fitted = phase.mean() + slope * tc
    residual = phase - fitted
    total = np.sum((phase - phase.mean())**2)
    r2 = 1 - np.sum(residual**2)/total if total > 1e-24 else 1.0
    increments = np.angle(z[1:] * np.conj(z[:-1]))
    return dict(s_phi=float(slope), intercept=float(phase.mean()-slope*t.mean()),
                wrapped=wrapped.tolist(), unwrapped=phase.tolist(),
                fitted=fitted.tolist(), residual=residual.tolist(),
                rmse=float(np.sqrt(np.mean(residual**2))), r2=float(r2),
                max_adjacent_step=float(np.max(abs(increments))),
                unwrap_continuity_valid=bool(np.max(abs(increments)) < max_step),
                unwrap_turn_corrections=np.rint((phase-wrapped)/(2*np.pi)).astype(int).tolist(),
                telescoping_error=float(np.sum(increments)-(phase[-1]-phase[0])))


def pair_observations(coefficients, times, lags=(1,)):
    """Direct raw-bin cross spectra; each lag class has total weight 1/L."""
    z, t = _series(coefficients, times)
    if len(set(lags)) != len(lags) or not lags or any(l < 1 or l >= len(t) for l in lags):
        raise ValueError('Distinct positive lag classes smaller than look count required')
    phases, dts, weights, labels = [], [], [], []
    for lag in lags:
        c = z[lag:] * z[:-lag].conj()
        phases.extend(np.angle(c)); dts.extend(t[lag:] - t[:-lag])
        weights.extend(np.full(len(c), 1/(len(lags)*len(c))))
        labels.extend([lag]*len(c))
    return tuple(np.asarray(v) for v in (phases, dts, weights, labels))


def circular_fit(phases, delta_t, weights, bounds, grid_size=2001,
                 alternative_cost_margin=0.01, max_rms=0.5):
    """Bounded global grid + refinement of EVERY grid-local minimum.

    Cost=sum normalized_weight*(1-cos(phi-s*dt)); no nominal dt, unwrap,
    expected period or confidence interval. Alternatives within an absolute
    cost margin are labelled ambiguous, not selected using external truth.
    """
    phi, dt, w = map(lambda x: np.asarray(x, float), (phases, delta_t, weights))
    lo, hi = map(float, bounds)
    if phi.ndim != 1 or phi.shape != dt.shape or phi.shape != w.shape or not phi.size:
        raise ValueError('Matching nonempty vectors required')
    if not np.all(np.isfinite([phi, dt, w])) or np.any(dt <= 0) or np.any(w < 0) or w.sum() <= 0:
        raise ValueError('Finite data, positive delta_t and nonnegative weights required')
    if not lo < hi or grid_size < 101:
        raise ValueError('Ordered bounds and grid_size >=101 required')
    w = w / w.sum()
    objective = lambda s: float(np.dot(w, 1-np.cos(phi-s*dt)))
    grid = np.linspace(lo, hi, grid_size)
    cost = (1-np.cos(phi[None, :]-grid[:, None]*dt)) @ w
    indices = np.where((cost[1:-1] <= cost[:-2]) & (cost[1:-1] <= cost[2:]))[0]+1
    minima = []
    for i in indices:
        opt = minimize_scalar(objective, bounds=(grid[i-1], grid[i+1]),
                              method='bounded', options={'xatol': 1e-12})
        minima.append(dict(s_phi=float(opt.x), cost=float(opt.fun), boundary=False))
    if cost[0] <= cost[1]: minima.append(dict(s_phi=lo, cost=float(cost[0]), boundary=True))
    if cost[-1] <= cost[-2]: minima.append(dict(s_phi=hi, cost=float(cost[-1]), boundary=True))
    minima.sort(key=lambda item: item['cost'])
    best = minima[0]
    residual = np.angle(np.exp(1j*(phi-best['s_phi']*dt)))
    rms = float(np.sqrt(np.dot(w, residual**2)))
    ambiguous = any(m['cost'] <= best['cost']+alternative_cost_margin for m in minima[1:])
    return dict(s_phi=best['s_phi'], cost=best['cost'], circular_rms=rms,
                residual=residual.tolist(), minima=minima, ambiguous=ambiguous,
                boundary=best['boundary'], valid=bool(not ambiguous and not best['boundary'] and rms <= max_rms))


def estimate_circular(coefficients, times, lags, bounds, **kwargs):
    phase, dt, w, labels = pair_observations(coefficients, times, lags)
    result = circular_fit(phase, dt, w, bounds, **kwargs)
    result.update(lags=list(lags), pair_count=len(phase),
                  delta_t=dt.tolist(), pair_phase=phase.tolist(),
                  pair_weights=w.tolist(), pair_lags=labels.tolist())
    return result
