"""Mudiyanselage et al. (2024)-inspired transect windows and
contour/blob spectral-peak identification on native Sentinel-1 IW SLC samples.

Reference: Mudiyanselage, Wilkinson, Abd-Elrahman, "Automated High-Resolution
Bathymetry from Sentinel-1 SAR Images in Deeper Nearshore Coastal Waters in
Eastern Florida", Remote Sens. 2024, 16, 1; code/data doi:10.17632/3dd2pb9j7t.1.

What is taken from the paper / its released code
------------------------------------------------
* square windows centred on points generated every 50 m along cross-shore
  transects (``deldist = 50``, ``Mask_len`` square clip), i.e. heavily
  overlapping windows (paper: 1280 m windows, 96 % overlap);
* 2-D FFT of each window; 20 contour levels, threshold = highest level;
  blobs = regions enclosed by that level, geometric centroids (paper text; primary);
* the released ``FastPeakFind`` helper (3x3 median, threshold, 7x7 Gaussian
  sigma=1, re-threshold 0.9, 8-connected weighted centroids, rejection of areas
  > mean + 2 std) is ported as a prefixed sensitivity: on synthetic speckled
  swell its 3x3 median removes the 1-3 pixel blobs left by the top-level
  threshold, so it is not the primary reading (decided before real pixels);
* the centroid of the largest blob closest to the origin, paired with its
  symmetric partner, gives wavelength (Eq. 3) and direction (Eq. 4);
* moving mean of wavelength along each transect.

Documented departures (physics / provenance, not tuning)
--------------------------------------------------------
* The paper works on GRD 10 m ground pixels.  Here no image resampling is done:
  the ground-wavenumber spectrum is evaluated exactly from native SLC samples
  (non-uniform DFT at their geolocated FRF positions).  This removes the
  bilinear/nearest gridding dependence found in Block37.
* The released MATLAB main script is not in the dataset; the contour scale
  (log10 magnitude), MATLAB-like level spacing and float (not uint16) arithmetic
  are frozen assumptions, with linear magnitude as a prefixed sensitivity.
* The paper estimates Tp from nautical-chart depth (Eq. 7).  That is circular
  for validation and is NOT used: period comes only from FRF measured spectra.

No function here accepts bathymetry, expected wavelength or omega.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import ndimage


# ---------------------------------------------------------------- geometry
def fit_frf_geo_affine(x, y, lon, lat):
    """Least-squares lon/lat = A [1, x, y]; returns coef (3x2) and residual metres."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    a = np.column_stack((np.ones(x.size), x, y))
    ll = np.column_stack((np.asarray(lon, float), np.asarray(lat, float)))
    coef = np.linalg.lstsq(a, ll, rcond=None)[0]
    res = a @ coef - ll
    lat0 = float(np.mean(ll[:, 1]))
    metres = np.column_stack((res[:, 0] * 111319.49 * math.cos(math.radians(lat0)),
                              res[:, 1] * 110574.0))
    err = np.linalg.norm(metres, axis=1)
    return coef, {"n_points": int(x.size), "residual_p50_m": float(np.median(err)),
                  "residual_p95_m": float(np.percentile(err, 95)),
                  "residual_max_m": float(err.max())}


def geo_to_frf(coef, lon, lat):
    coef = np.asarray(coef, float)
    m = coef[1:, :].T                      # [[dlon/dx, dlon/dy],[dlat/dx, dlat/dy]]
    d = np.stack((np.asarray(lon, float) - coef[0, 0], np.asarray(lat, float) - coef[0, 1]))
    xy = np.linalg.solve(m, d.reshape(2, -1))
    return xy[0].reshape(np.shape(lon)), xy[1].reshape(np.shape(lon))


def frf_to_geo(coef, x, y):
    coef = np.asarray(coef, float)
    x = np.asarray(x, float); y = np.asarray(y, float)
    return coef[0, 0] + coef[1, 0]*x + coef[2, 0]*y, coef[0, 1] + coef[1, 1]*x + coef[2, 1]*y


def frf_axis_bearings(coef, lat0):
    """True bearings of +xFRF and +yFRF (degrees clockwise from north)."""
    coef = np.asarray(coef, float); c = math.cos(math.radians(lat0))
    out = []
    for i in (1, 2):
        e = coef[i, 0] * 111319.49 * c; n = coef[i, 1] * 110574.0
        out.append(math.degrees(math.atan2(e, n)) % 360)
    return out


def en_to_frf_matrix(coef, lat0):
    """Matrix M with [x,y]_FRF = M @ [E,N] for small displacements (metres)."""
    coef = np.asarray(coef, float); c = math.cos(math.radians(lat0))
    j = np.array([[coef[1, 0]*111319.49*c, coef[2, 0]*111319.49*c],
                  [coef[1, 1]*110574.0, coef[2, 1]*110574.0]])   # dEN/dxy
    return np.linalg.inv(j)


# ---------------------------------------------------------------- native reads
def native_window_bounds(center_sample, center_line, n_samples, n_lines):
    s0 = int(round(center_sample - n_samples/2)); l0 = int(round(center_line - n_lines/2))
    return s0, l0, s0 + n_samples, l0 + n_lines


def window_inside_burst(annotation, burst_index, s0, l0, s1, l1):
    """True only if every sample of [l0,l1) x [s0,s1) is valid in one burst."""
    burst = annotation["bursts"][burst_index]
    first = np.asarray(burst["first_valid_sample"]); last = np.asarray(burst["last_valid_sample"])
    local = np.arange(l0, l1) - burst["line_start"]
    if local.min() < 0 or local.max() >= first.size:
        return False, "window leaves burst lines"
    f = first[local]; g = last[local]
    if np.any(f < 0):
        return False, "window contains invalid burst lines"
    if s0 < f.max() or s1 - 1 > g.min():
        return False, "window leaves valid samples"
    return True, "all samples valid in a single burst; no seam"


def read_native(tiff, s0, l0, s1, l1, expected_shape=None):
    import rasterio
    from rasterio.windows import Window
    with rasterio.open(tiff) as ds:
        if expected_shape and (ds.height, ds.width) != tuple(expected_shape):
            raise ValueError("TIFF/annotation dimension mismatch")
        dn = ds.read(1, window=Window(s0, l0, s1 - s0, l1 - l0))
    if not np.iscomplexobj(dn):
        raise ValueError("Expected complex SLC samples")
    if dn.shape != (l1 - l0, s1 - s0):
        raise ValueError("Short window read")
    return dn


# ---------------------------------------------------------------- spectrum
def plane_detrend(z, x, y):
    a = np.column_stack((np.ones(z.size), (x - x.mean()).ravel(), (y - y.mean()).ravel()))
    beta = np.linalg.lstsq(a, z.ravel(), rcond=None)[0]
    return z - (a @ beta).reshape(z.shape)


def hann2(shape):
    return np.hanning(shape[0])[:, None] * np.hanning(shape[1])[None, :]


def k_grid(window_m, padding, kmax):
    dk = 2*np.pi/(window_m*padding)
    n = int(np.floor(kmax/dk))
    k = np.arange(-n, n + 1) * dk
    return k, dk


def nudft_magnitude(z, x, y, kx, ky, chunk=256):
    """|sum z exp(-i (kx x + ky y))| on the (ky, kx) grid; negative exponent as numpy.fft."""
    z = np.asarray(z, float).ravel(); x = np.asarray(x, float).ravel(); y = np.asarray(y, float).ravel()
    KX, KY = np.meshgrid(kx, ky)
    kxf = KX.ravel(); kyf = KY.ravel(); out = np.empty(kxf.size, complex)
    for i in range(0, kxf.size, chunk):
        ph = np.outer(kxf[i:i+chunk], x) + np.outer(kyf[i:i+chunk], y)
        out[i:i+chunk] = np.exp(-1j*ph) @ z
    return np.abs(out).reshape(KX.shape)


def search_mask(kx, ky, exclusion_k, kmax_by_axis=None):
    """Excludes |k| < exclusion_k and, optionally, components beyond sampling limits
    along given unit axes [(ux,uy,kmax),...] expressed in FRF coordinates."""
    KX, KY = np.meshgrid(kx, ky)
    m = np.hypot(KX, KY) >= exclusion_k
    for ux, uy, lim in (kmax_by_axis or []):
        m &= np.abs(KX*ux + KY*uy) <= lim
    return m


# ---------------------------------------------------------------- paper peak
def matlab_like_levels(zmin, zmax, n):
    """n evenly spaced interior levels (frozen reading of MATLAB contour(Z,n))."""
    return np.linspace(zmin, zmax, n + 2)[1:-1]


def fastpeakfind_centroids(d, thres, sigma=1.0, size=7):
    """Float port of FastPeakFind(d, thres, fspecial('gaussian',7,1), edg, res=2)."""
    d = np.asarray(d, float)
    d = ndimage.median_filter(d, size=3, mode="constant", cval=0.0)
    d = d * (d > thres)
    if not np.any(d):
        return []
    ax = np.arange(size) - (size - 1)/2
    g = np.exp(-(ax[:, None]**2 + ax[None, :]**2)/(2*sigma**2)); g /= g.sum()
    d = ndimage.convolve(d, g, mode="constant", cval=0.0)
    d = d * (d > 0.9*thres)
    lab, n = ndimage.label(d > 0, structure=np.ones((3, 3), int))
    blobs = []
    for i in range(1, n + 1):
        m = lab == i
        w = d[m]; iy, ix = np.nonzero(m)
        blobs.append({"area_px": int(m.sum()),
                      "centroid_row": float((iy*w).sum()/w.sum()),
                      "centroid_col": float((ix*w).sum()/w.sum()),
                      "max_value": float(w.max()), "mask": m})
    if len(blobs) > 1:
        areas = np.array([b["area_px"] for b in blobs], float)
        keep = areas <= areas.mean() + 2*areas.std()
        blobs = [b for b, k in zip(blobs, keep) if k]
    return blobs


def contour_blobs(d, thres):
    """Paper text reading: regions enclosed by the highest contour level
    (8-connected pixels strictly above it) with *geometric* centroids."""
    lab, n = ndimage.label(np.asarray(d) > thres, structure=np.ones((3, 3), int))
    blobs = []
    for i in range(1, n + 1):
        m = lab == i
        iy, ix = np.nonzero(m)
        blobs.append({"area_px": int(m.sum()), "centroid_row": float(iy.mean()),
                      "centroid_col": float(ix.mean()), "max_value": float(np.asarray(d)[m].max()),
                      "mask": m})
    return blobs


def paper_peak(magnitude, kx, ky, mask, *, n_levels=20, scale="log10", blob_method="contour",
               ambiguity_area_ratio=0.8, ambiguity_rel_wavelength=0.15):
    """SAR-only peak identification.  Signature deliberately has no depth/omega input."""
    mag = np.asarray(magnitude, float)
    if scale == "log10":
        s = np.log10(np.maximum(mag, np.finfo(float).tiny))
    elif scale == "linear":
        s = mag.copy()
    else:
        raise ValueError("scale must be log10 or linear")
    vals = s[mask]
    zmin, zmax = float(vals.min()), float(vals.max())
    levels = matlab_like_levels(zmin, zmax, n_levels)
    shifted = np.where(mask, s - zmin, 0.0)
    thres = float(levels[-1] - zmin)
    if blob_method == "contour":
        blobs = contour_blobs(shifted, thres)
    elif blob_method == "fastpeakfind":
        blobs = fastpeakfind_centroids(shifted, thres)
    else:
        raise ValueError("blob_method must be contour or fastpeakfind")
    dkx = kx[1]-kx[0]; dky = ky[1]-ky[0]
    out = []
    for b in blobs:
        cx = kx[0] + b["centroid_col"]*dkx; cy = ky[0] + b["centroid_row"]*dky
        kmag = math.hypot(cx, cy)
        if kmag == 0:
            continue
        canonical = cx > 0 or (abs(cx) < 1e-12 and cy > 0)
        out.append({"area_px": b["area_px"], "kx": cx, "ky": cy, "k": kmag,
                    "wavelength_m": 2*np.pi/kmag, "canonical": canonical,
                    "max_level_value": b["max_value"] + zmin})
    cand = [b for b in out if b["canonical"]]
    result = {"levels": levels.tolist(), "threshold": float(levels[-1]), "scale": scale,
              "blob_method": blob_method,
              "n_blobs_total": len(out), "blobs_canonical": sorted(cand, key=lambda b: (-b["area_px"], b["k"]))}
    if not cand:
        result.update(status="no_blob_above_top_level")
        return result
    ranked = result["blobs_canonical"]
    sel = ranked[0]
    partner = next((b for b in out if not b["canonical"] and
                    math.hypot(b["kx"] + sel["kx"], b["ky"] + sel["ky"]) <= 1.5*max(abs(dkx), abs(dky))), None)
    ambiguous = any(b is not sel and b["area_px"] >= ambiguity_area_ratio*sel["area_px"] and
                    abs(b["wavelength_m"] - sel["wavelength_m"])/sel["wavelength_m"] > ambiguity_rel_wavelength
                    for b in ranked)
    # Paper Eq. 3/4: separation of the symmetric pair; with an exact partner this is 2|k|.
    if partner is not None:
        sep = math.hypot(sel["kx"] - partner["kx"], sel["ky"] - partner["ky"])/2
    else:
        sep = sel["k"]
    result.update(status="ambiguous_multiple_blobs" if ambiguous else "identified",
                  selected=sel, symmetric_partner_found=partner is not None,
                  k_rad_m=float(sep), wavelength_m=float(2*np.pi/sep),
                  kx=float(sel["kx"]), ky=float(sel["ky"]))
    return result


def argmax_peak(magnitude, kx, ky, mask):
    """Block37-style global maximum (power) with quadratic log refinement, same grid."""
    p = np.where(mask, np.asarray(magnitude, float)**2, -np.inf)
    KX, _ = np.meshgrid(kx, ky)
    p = np.where(KX >= 0, p, -np.inf)
    iy, ix = np.unravel_index(np.argmax(p), p.shape)
    lp = np.log(np.maximum(np.asarray(magnitude, float)**2, np.finfo(float).tiny))

    def off(a, b, c):
        den = a - 2*b + c
        return float(np.clip(.5*(a - c)/den, -.5, .5)) if np.isfinite(den) and den < 0 else 0.0
    ox = off(lp[iy, ix-1], lp[iy, ix], lp[iy, ix+1]) if 0 < ix < len(kx)-1 else 0.0
    oy = off(lp[iy-1, ix], lp[iy, ix], lp[iy+1, ix]) if 0 < iy < len(ky)-1 else 0.0
    kxf = kx[ix] + ox*(kx[1]-kx[0]); kyf = ky[iy] + oy*(ky[1]-ky[0])
    k = math.hypot(kxf, kyf)
    return {"kx": float(kxf), "ky": float(kyf), "k_rad_m": k, "wavelength_m": 2*np.pi/k,
            "index": [int(iy), int(ix)]}


def lobe_to_annulus(magnitude, kx, ky, mask, kx0, ky0, dk):
    p = np.asarray(magnitude, float)**2
    KX, KY = np.meshgrid(kx, ky); kr = np.hypot(KX, KY); k0 = math.hypot(kx0, ky0)
    near = np.hypot(KX - kx0, KY - ky0) <= 1.5*dk
    ann = (np.abs(kr - k0) <= dk) & mask & ~near & ~(np.hypot(KX + kx0, KY + ky0) <= 1.5*dk)
    if not np.any(near) or not np.any(ann):
        return float("nan")
    return float(p[near].max()/np.median(p[ann]))


def bearing_from_frf_k(kx, ky, frf_x_bearing, frf_y_bearing):
    """True axial bearing of the wave vector given FRF axis bearings (both unit, ~orthogonal)."""
    bx = math.radians(frf_x_bearing); by = math.radians(frf_y_bearing)
    e = kx*math.sin(bx) + ky*math.sin(by); n = kx*math.cos(bx) + ky*math.cos(by)
    return math.degrees(math.atan2(e, n)) % 180


def moving_mean(values, valid, window=5, min_count=3):
    v = np.asarray(values, float); ok = np.asarray(valid, bool) & np.isfinite(v)
    out = np.full(v.shape, np.nan); h = window//2
    for i in range(v.size):
        if not ok[i]:
            continue
        sl = slice(max(0, i-h), min(v.size, i+h+1))
        w = v[sl][ok[sl]]
        if w.size >= min_count:
            out[i] = w.mean()
    return out


def depth_from_wavelength_period(wavelength, period, g=9.80665):
    """Paper Eq. 5, h = L/(2 pi) atanh(2 pi L /(g T^2)); NaN outside the domain."""
    r = 2*np.pi*wavelength/(g*period**2)
    return float(wavelength/(2*np.pi)*np.arctanh(r)) if 0 < r < 1 else float("nan")


def minimum_period(lambda_max, g=9.80665):
    """Paper Eq. 6: T_min = sqrt(2 pi lambda_max / g)."""
    return math.sqrt(2*np.pi*lambda_max/g)


def axial_difference(a, b):
    return abs((float(a) - float(b) + 90) % 180 - 90)
