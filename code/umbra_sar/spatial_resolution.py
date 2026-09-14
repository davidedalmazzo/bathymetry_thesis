"""Window-resolution primitives for Block15H; no SAR formation or fitting."""
from __future__ import annotations

import numpy as np


def tukey_1d(n: int, alpha: float = .1) -> np.ndarray:
    if n < 2 or not 0 <= alpha <= 1:
        raise ValueError('n >= 2 and alpha in [0,1] required')
    x = np.linspace(0., 1., n); w = np.ones(n); e = alpha / 2
    if alpha:
        left, right = x < e, x > 1-e
        w[left] = .5*(1+np.cos(np.pi*(2*x[left]/alpha-1)))
        w[right] = .5*(1+np.cos(np.pi*(2*x[right]/alpha-2/alpha+1)))
    return w


def window_2d(shape: tuple[int, int], alpha: float = .1) -> np.ndarray:
    return np.outer(tukey_1d(shape[0], alpha), tukey_1d(shape[1], alpha))


def _crossing(x: np.ndarray, y: np.ndarray, level: float) -> float:
    hit = np.flatnonzero(y <= level)
    if not len(hit): return float('nan')
    i = int(hit[0])
    if i == 0: return float(x[0])
    return float(x[i-1] + (level-y[i-1])*(x[i]-x[i-1])/(y[i]-y[i-1]))


def window_axis_metrics(n: int, alpha: float = .1, nfft: int = 262144) -> dict:
    """Power-kernel metrics in native FFT-bin units, measured numerically."""
    if nfft < 16*n: raise ValueError('nfft must densely sample one DFT period')
    w = tukey_1d(n, alpha)
    f = np.fft.fftshift(np.fft.fftfreq(nfft, d=1.0))*n
    p = abs(np.fft.fftshift(np.fft.fft(w, nfft)))**2
    p /= p[nfft//2]
    c = nfft//2; posx, posp = f[c:], p[c:]
    half = _crossing(posx, posp, .5)
    # A sampled Tukey need not have an exact analytic zero. The first local
    # minimum is the reproducible numerical main-lobe boundary.
    minima = np.flatnonzero((posp[1:-1] <= posp[:-2]) & (posp[1:-1] <= posp[2:]))+1
    first = int(minima[0]) if len(minima) else None
    first_x = float(posx[first]) if first is not None else float('nan')
    maxima = (np.flatnonzero((posp[1:-1] >= posp[:-2]) & (posp[1:-1] >= posp[2:]))+1) if first is not None else []
    maxima = [int(i) for i in maxima if i > first]
    side_i = maxima[0] if maxima else None
    side = float(posp[side_i]) if side_i is not None else float('nan')
    dx = float(f[1]-f[0]); main = float(np.sum(p[np.abs(f) <= first_x])*dx) if first is not None else float('nan')
    total = float(np.sum(p)*dx)
    enbw = float(n*np.sum(w*w)/np.sum(w)**2)
    return dict(n=n, alpha=alpha, delta_bin=1/n, fwhm_power_bins=2*half,
        equivalent_lobe_width_bins=total, enbw_bins=enbw,
        first_minimum_bins=first_x, exact_first_zero_defined=False,
        first_minimum_power=float(posp[first]) if first is not None else float('nan'),
        first_sidelobe_power=side, first_sidelobe_db=float(10*np.log10(side)) if side > 0 else float('-inf'),
        main_lobe_energy_fraction=main/total if total else float('nan'),
        sidelobe_to_main_energy=(total-main)/main if main else float('nan'))


def kernel_overlap(shape: tuple[int, int], alpha: float, delta_row: int, delta_col: int) -> float:
    """Correlation of neighboring windowed-DFT bins for spatial white input."""
    w2 = window_2d(shape, alpha)**2
    r = np.arange(shape[0])[:, None]; c = np.arange(shape[1])[None, :]
    phase = np.exp(-2j*np.pi*(delta_row*r/shape[0] + delta_col*c/shape[1]))
    return float(abs(np.sum(w2*phase)/np.sum(w2)))


def count_local_maxima(power: np.ndarray, relative_floor: float = .05) -> list[tuple[int, int]]:
    """Non-periodic 3x3 maxima; conjugates are deliberately not deduplicated."""
    a=np.asarray(power,float); out=[]; threshold=float(np.max(a))*relative_floor
    for i in range(1,a.shape[0]-1):
        for j in range(1,a.shape[1]-1):
            if a[i,j] >= threshold and a[i,j] == np.max(a[i-1:i+2,j-1:j+2]): out.append((i,j))
    return out
