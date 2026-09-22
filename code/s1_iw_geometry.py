"""Burst-aware Sentinel-1 IW SLC geolocation (image <-> lon/lat).

The annotation geolocation grid has one row per burst start (lines 0, 1508, ...)
with the azimuth time of that burst.  Consecutive bursts overlap in time, so a
burst spans lines_per_burst * azimuthTimeInterval (~3.10 s) while grid rows are
only ~2.76 s apart.  Interpolating the grid linearly in *line number* therefore
compresses azimuth time by ~12 % and misplaces pixels by up to ~1.5 km.  Here a
pixel (sample, line) is mapped to azimuth time
    t = t_burst(b) + (line - b * lines_per_burst) * azimuthTimeInterval,
and the grid is interpolated in (azimuth time, range sample).  Verified at Duck
against the survey z=0 contour: median 0.8 samples (vs 74 samples for the
line-number model).
"""
from __future__ import annotations

import math

import numpy as np
from scipy.interpolate import LinearNDInterpolator, RegularGridInterpolator


def _ts(value):
    from datetime import datetime, timezone
    if isinstance(value, str):
        v = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.timestamp()
    return value.timestamp()


class SwathGeometry:
    def __init__(self, annotation):
        self.ann = annotation
        self.swath = annotation["swath"]
        self.lpb = int(annotation["lines_per_burst"])
        self.ati = float(annotation["azimuth_time_interval_s"])
        self.nsamples = int(annotation["number_of_samples"]); self.nlines = int(annotation["number_of_lines"])
        pts = annotation["geolocation_grid"]
        self.t0 = min(_ts(p["azimuthTime"]) for p in pts)
        self.burst_t = np.array([_ts(b["azimuth_time"]) - self.t0 for b in annotation["bursts"]])
        t = np.array([_ts(p["azimuthTime"]) - self.t0 for p in pts]); s = np.array([p["pixel"] for p in pts], float)
        lon = np.array([p["longitude"] for p in pts]); lat = np.array([p["latitude"] for p in pts])
        inc = np.array([p["incidenceAngle"] for p in pts])
        rows = np.unique(np.round(t, 6)); cols = np.unique(s)
        if rows.size * cols.size == t.size:
            order = np.lexsort((s, np.round(t, 6)))
            shape = (rows.size, cols.size)
            tt = t[order].reshape(shape).mean(axis=1)
            method = "cubic" if min(shape) >= 4 else "linear"   # smooth (C1) geolocation surface
            self._lon = RegularGridInterpolator((tt, cols), lon[order].reshape(shape), method=method, bounds_error=False, fill_value=None)
            self._lat = RegularGridInterpolator((tt, cols), lat[order].reshape(shape), method=method, bounds_error=False, fill_value=None)
            self._inc = RegularGridInterpolator((tt, cols), inc[order].reshape(shape), bounds_error=False, fill_value=None)
        else:                                   # irregular grid fallback
            self._lon = LinearNDInterpolator(np.column_stack((t, s)), lon)
            self._lat = LinearNDInterpolator(np.column_stack((t, s)), lat)
            self._inc = LinearNDInterpolator(np.column_stack((t, s)), inc)
        self._inv_t = LinearNDInterpolator(np.column_stack((lon, lat)), t)
        self._inv_s = LinearNDInterpolator(np.column_stack((lon, lat)), s)
        self.t_range = (t.min(), t.max())

    # -- time/line
    def line_time(self, line):
        line = np.asarray(line, float)
        b = np.clip(np.floor(line / self.lpb).astype(int), 0, len(self.burst_t) - 1)
        return self.burst_t[b] + (line - b * self.lpb) * self.ati

    def _eval(self, interp, t, s):
        t = np.asarray(t, float); s = np.asarray(s, float)
        pts = np.column_stack((t.ravel(), s.ravel()))
        return np.asarray(interp(pts)).reshape(np.broadcast(t, s).shape)

    def forward(self, sample, line):
        t = self.line_time(line)
        sample = np.broadcast_to(np.asarray(sample, float), np.shape(t))
        return self._eval(self._lon, t, sample), self._eval(self._lat, t, sample)

    def incidence(self, sample, line):
        return self._eval(self._inc, self.line_time(line), sample)

    def geo_to_time_sample(self, lon, lat, iterations=3):
        """Inverse to (azimuth time, sample), refined so forward(inverse(p)) == p."""
        lon = np.asarray(lon, float); lat = np.asarray(lat, float)
        t = np.asarray(self._inv_t(lon, lat), float); s = np.asarray(self._inv_s(lon, lat), float)
        for _ in range(iterations):
            ok = np.isfinite(t) & np.isfinite(s)
            if not np.any(ok):
                break
            dt, ds = 1e-3, 1.0
            f = lambda tt, ss: (self._eval(self._lon, tt, ss), self._eval(self._lat, tt, ss))
            lo0, la0 = f(t, s); lo_t, la_t = f(t + dt, s); lo_s, la_s = f(t, s + ds)
            j11 = (lo_t - lo0) / dt; j12 = (lo_s - lo0) / ds; j21 = (la_t - la0) / dt; j22 = (la_s - la0) / ds
            det = j11 * j22 - j12 * j21
            rl = lon - lo0; ra = lat - la0
            t = t + np.where(ok, (j22 * rl - j12 * ra) / det, 0)
            s = s + np.where(ok, (-j21 * rl + j11 * ra) / det, 0)
        return t, s

    def candidates(self, lon, lat):
        """All (burst, line, sample) that image the point on valid lines."""
        t, s = self.geo_to_time_sample(lon, lat)
        out = []
        if not (np.isfinite(t) and np.isfinite(s)):
            return out
        for b, tb in enumerate(self.burst_t):
            rel = (float(t) - tb) / self.ati
            if 0 <= rel < self.lpb:
                first = self.ann["bursts"][b]["first_valid_sample"]; last = self.ann["bursts"][b]["last_valid_sample"]
                li = int(rel)
                if first[li] >= 0 and first[li] <= s <= last[li]:
                    valid_lines = [i for i, v in enumerate(first) if v >= 0]
                    margin = min(rel - valid_lines[0], valid_lines[-1] - rel)
                    out.append({"burst": b, "line": b * self.lpb + rel, "sample": float(s), "line_margin": margin})
        return sorted(out, key=lambda c: -c["line_margin"])

    def ground_spacing(self, sample, line, to_metres):
        """Local ground spacing (m) per sample and per line; to_metres(lon,lat)->(E,N)."""
        e0 = np.array(to_metres(*self.forward(sample, line)))
        es = np.array(to_metres(*self.forward(sample + 1, line)))
        el = np.array(to_metres(*self.forward(sample, line + 1)))
        return float(np.linalg.norm(es - e0)), float(np.linalg.norm(el - e0)), (es - e0), (el - e0)


def window_inside_single_burst(annotation, burst, s0, l0, s1, l1):
    b = annotation["bursts"][burst]
    first = np.asarray(b["first_valid_sample"]); last = np.asarray(b["last_valid_sample"])
    loc = np.arange(l0, l1) - burst * annotation["lines_per_burst"]
    if loc.min() < 0 or loc.max() >= first.size:
        return False
    f = first[loc]; g = last[loc]
    return bool(np.all(f >= 0) and s0 >= f.max() and s1 - 1 <= g.min())


class GrdGeometry(SwathGeometry):
    """GRD: lines are uniform in azimuth time (no bursts), so the grid is
    interpolated in (line, pixel).  Exposes the SwathGeometry interface with a
    single pseudo-burst and 'time' == line."""

    def __init__(self, annotation):
        self.ann = annotation; self.swath = annotation["swath"]
        self.nsamples = int(annotation["number_of_samples"]); self.nlines = int(annotation["number_of_lines"])
        self.lpb = self.nlines; self.ati = 1.0; self.burst_t = np.array([0.0]); self.t0 = 0.0
        pts = annotation["geolocation_grid"]
        ln = np.array([p["line"] for p in pts], float); s = np.array([p["pixel"] for p in pts], float)
        lon = np.array([p["longitude"] for p in pts]); lat = np.array([p["latitude"] for p in pts])
        inc = np.array([p["incidenceAngle"] for p in pts])
        rows = np.unique(ln); cols = np.unique(s)
        order = np.lexsort((s, ln)); shape = (rows.size, cols.size)
        if rows.size * cols.size != ln.size:
            raise ValueError("irregular GRD geolocation grid")
        method = "cubic" if min(shape) >= 4 else "linear"
        mk = lambda v, m: RegularGridInterpolator((rows, cols), v[order].reshape(shape), method=m, bounds_error=False, fill_value=None)
        self._lon = mk(lon, method); self._lat = mk(lat, method); self._inc = mk(inc, "linear")
        self._inv_t = LinearNDInterpolator(np.column_stack((lon, lat)), ln)
        self._inv_s = LinearNDInterpolator(np.column_stack((lon, lat)), s)
        self.t_range = (ln.min(), ln.max())

    def line_time(self, line):
        return np.asarray(line, float)

    def candidates(self, lon, lat):
        t, s = self.geo_to_time_sample(lon, lat)
        if not (np.isfinite(t) and np.isfinite(s)) or not (0 <= t < self.nlines and 0 <= s < self.nsamples):
            return []
        return [{"burst": 0, "line": float(t), "sample": float(s), "line_margin": float(min(t, self.nlines - t))}]


def parse_grd_annotation(path):
    """Minimal GRD annotation reader returning the keys used by s1_transect_bathy."""
    from lxml import etree
    root = etree.parse(str(path), etree.XMLParser(resolve_entities=False, no_network=True)).getroot()
    one = lambda n: root.xpath(f'.//*[local-name()="{n}"]')[0].text.strip()
    pts = []
    for node in root.xpath('.//*[local-name()="geolocationGridPoint"]'):
        v = {etree.QName(c).localname: c.text for c in node}
        pts.append({"line": int(v["line"]), "pixel": int(v["pixel"]), "latitude": float(v["latitude"]),
                    "longitude": float(v["longitude"]), "incidenceAngle": float(v["incidenceAngle"])})
    nl = int(one("numberOfLines")); ns = int(one("numberOfSamples"))
    return {"swath": one("swath"), "polarisation": one("polarisation"), "product_type": one("productType"),
            "number_of_lines": nl, "number_of_samples": ns, "lines_per_burst": nl,
            "range_pixel_spacing_m": float(one("rangePixelSpacing")), "azimuth_pixel_spacing_m": float(one("azimuthPixelSpacing")),
            "geolocation_grid": pts,
            "bursts": [{"first_valid_sample": [0] * nl, "last_valid_sample": [ns - 1] * nl, "line_start": 0}]}
