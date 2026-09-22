"""Block37 Sentinel-1 intensity-domain spatial spectrum utilities.

The routines deliberately have no bathymetry input: SAR peak selection is made
from the intensity spectrum alone.  Coordinates are FRF x/y metres unless an
East/North quantity is explicitly named.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path

import numpy as np
from lxml import etree
from scipy.interpolate import LinearNDInterpolator, RegularGridInterpolator
from scipy.ndimage import map_coordinates
from scipy.signal.windows import tukey


def _xml(path: Path):
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
    return etree.parse(str(path), parser).getroot()


def _children(node):
    return {etree.QName(child).localname: (child.text or "").strip() for child in node}


def _numbers(text, dtype=float):
    return np.asarray([dtype(item) for item in text.split()], dtype=dtype)


def parse_calibration_lut(path: Path):
    root = _xml(path)
    nodes = root.xpath('.//*[local-name()="calibrationVector"]')
    if not nodes:
        raise ValueError("No calibration vectors")
    lines, pixels, values = [], None, []
    for node in nodes:
        item = _children(node)
        line = int(item["line"])
        px = _numbers(item["pixel"], int)
        sigma = _numbers(item["sigmaNought"])
        if px.size != sigma.size or px.size < 2:
            raise ValueError("Malformed calibration LUT")
        if pixels is None:
            pixels = px
        elif not np.array_equal(pixels, px):
            raise ValueError("Non-rectangular calibration LUT is unsupported")
        lines.append(line)
        values.append(sigma)
    lines = np.asarray(lines, float)
    values = np.asarray(values, float)
    if np.any(np.diff(lines) <= 0) or np.any(np.diff(pixels) <= 0) or np.any(values <= 0):
        raise ValueError("Invalid calibration LUT axes/values")
    interp = RegularGridInterpolator((lines, pixels.astype(float)), values,
                                     bounds_error=False, fill_value=None)
    return {"lines": lines, "pixels": pixels.astype(float), "values": values,
            "interpolator": interp, "formula": "sigma0=|DN|^2/sigmaNought^2"}


def parse_noise_lut(path: Path):
    """Parse IPF 3.x range and azimuth multiplicative noise factors."""
    root = _xml(path)
    range_nodes = root.xpath('.//*[local-name()="noiseRangeVector"]')
    points, vals = [], []
    for node in range_nodes:
        item = _children(node)
        line = float(item["line"])
        px = _numbers(item["pixel"])
        lut = _numbers(item["noiseRangeLut"])
        if px.size != lut.size:
            raise ValueError("Malformed range-noise LUT")
        points.extend((line, float(p)) for p in px)
        vals.extend(float(v) for v in lut)
    if not points:
        raise ValueError("No range-noise vectors")
    range_interp = LinearNDInterpolator(np.asarray(points), np.asarray(vals), fill_value=np.nan)
    azimuth = []
    for node in root.xpath('.//*[local-name()="noiseAzimuthVector"]'):
        item = _children(node)
        lines = _numbers(item["line"])
        lut = _numbers(item["noiseAzimuthLut"])
        if lines.size != lut.size:
            raise ValueError("Malformed azimuth-noise LUT")
        azimuth.append({
            "swath": item.get("swath", "").upper(),
            "first_azimuth_line": int(item["firstAzimuthLine"]),
            "last_azimuth_line": int(item["lastAzimuthLine"]),
            "first_range_sample": int(item["firstRangeSample"]),
            "last_range_sample": int(item["lastRangeSample"]),
            "lines": lines,
            "lut": lut,
        })
    return {"range_interpolator": range_interp, "azimuth_vectors": azimuth,
            "formula": "sigma0_noise_sub=(|DN|^2-noiseRangeLut*noiseAzimuthLut)/sigmaNought^2"}


def evaluate_noise(lut, lines, samples, swath="IW3"):
    lines = np.asarray(lines, float)
    samples = np.asarray(samples, float)
    result = np.full(lines.shape, np.nan)
    for item in lut["azimuth_vectors"]:
        if item["swath"] and item["swath"] != swath.upper():
            continue
        mask = ((lines >= item["first_azimuth_line"]) &
                (lines <= item["last_azimuth_line"]) &
                (samples >= item["first_range_sample"]) &
                (samples <= item["last_range_sample"]))
        if np.any(mask):
            az = np.interp(lines[mask], item["lines"], item["lut"])
            rng = lut["range_interpolator"](np.column_stack((lines[mask], samples[mask])))
            result[mask] = rng * az
    # Some products omit azimuth factors. In that case range LUT is complete.
    missing = ~np.isfinite(result)
    if np.any(missing) and not lut["azimuth_vectors"]:
        result[missing] = lut["range_interpolator"](
            np.column_stack((lines[missing], samples[missing])))
    return result


def calibrated_power(dn, calibration, lines, samples, noise=None):
    raw = np.abs(np.asarray(dn)) ** 2
    points = np.column_stack((np.asarray(lines).ravel(), np.asarray(samples).ravel()))
    sigma = calibration["interpolator"](points).reshape(raw.shape)
    if noise is not None:
        raw = raw - np.asarray(noise)
    output = raw / sigma**2
    output[raw <= 0] = np.nan
    return output


def fit_frf_affine(bounds, geojson):
    xmin, xmax, ymin, ymax = map(float, bounds)
    xy = np.asarray([[xmin, ymin], [xmax, ymin], [xmax, ymax], [xmin, ymax]], float)
    ll = np.asarray(geojson["coordinates"][0][:4], float)
    design = np.column_stack((np.ones(4), xy))
    coef = np.linalg.lstsq(design, ll, rcond=None)[0]
    residual = design @ coef - ll
    return coef, float(np.max(np.linalg.norm(residual, axis=1)))


def frf_to_geo(coef, x, y):
    shape = np.broadcast_shapes(np.shape(x), np.shape(y))
    x = np.broadcast_to(x, shape)
    y = np.broadcast_to(y, shape)
    p = np.column_stack((np.ones(x.size), x.ravel(), y.ravel())) @ np.asarray(coef)
    return p[:, 0].reshape(shape), p[:, 1].reshape(shape)


def frf_en_basis(coef, origin_xy):
    """Local East/North metres per one FRF x/y metre (small-angle WGS84)."""
    x, y = origin_xy
    lon0, lat0 = frf_to_geo(coef, x, y)
    lonx, latx = frf_to_geo(coef, x + 1, y)
    lony, laty = frf_to_geo(coef, x, y + 1)
    r = 6378137.0
    scale_lon = r * math.cos(math.radians(float(lat0))) * math.pi / 180
    scale_lat = r * math.pi / 180
    return np.asarray([[(float(lonx)-float(lon0))*scale_lon,
                        (float(lony)-float(lon0))*scale_lon],
                       [(float(latx)-float(lat0))*scale_lat,
                        (float(laty)-float(lat0))*scale_lat]])


def grid_coordinates(center, size, spacing):
    nx = int(round(size[0] / spacing[0]))
    ny = int(round(size[1] / spacing[1]))
    x = center[0] + (np.arange(nx) - (nx - 1) / 2) * spacing[0]
    y = center[1] + (np.arange(ny) - (ny - 1) / 2) * spacing[1]
    return np.meshgrid(x, y)


def valid_queries(annotation, lines, samples, order=1, burst_index=0):
    burst = annotation["bursts"][burst_index]
    floors = np.floor(lines).astype(int)
    ceils = np.ceil(lines).astype(int) if order else floors
    s0 = np.floor(samples).astype(int)
    s1 = np.ceil(samples).astype(int) if order else s0
    ok = np.ones(lines.shape, bool)
    for target_line in np.unique(np.concatenate((floors.ravel(), ceils.ravel()))):
        mask = (floors == target_line) | (ceils == target_line)
        local = target_line - burst["line_start"]
        if local < 0 or local >= len(burst["first_valid_sample"]):
            ok[mask] = False
            continue
        first = burst["first_valid_sample"][local]
        last = burst["last_valid_sample"][local]
        ok[mask] &= first >= 0
        ok[mask] &= s0[mask] >= first
        ok[mask] &= s1[mask] <= last
    return ok


def read_resampled_complex(tiff, annotation, geo_grid, coef, xx, yy, order=1, burst_index=0):
    from rasterio.windows import Window
    import rasterio

    lon, lat = frf_to_geo(coef, xx, yy)
    samples = np.empty(xx.shape); lines = np.empty(xx.shape)
    for index in np.ndindex(xx.shape):
        samples[index], lines[index] = geo_grid.geo_to_image(float(lon[index]), float(lat[index]))
    if not np.all(np.isfinite(samples + lines)):
        raise ValueError("FRF grid outside annotation geolocation support")
    valid = valid_queries(annotation, lines, samples, order=order, burst_index=burst_index)
    if not np.all(valid):
        raise ValueError("FRF grid interpolation footprint leaves exact burst valid support")
    col0 = max(0, int(np.floor(samples.min())) - 1)
    row0 = max(0, int(np.floor(lines.min())) - 1)
    col1 = min(annotation["number_of_samples"], int(np.ceil(samples.max())) + 2)
    row1 = min(annotation["number_of_lines"], int(np.ceil(lines.max())) + 2)
    window = Window(col0, row0, col1-col0, row1-row0)
    with rasterio.open(tiff) as ds:
        if ds.count != 1 or ds.width != annotation["number_of_samples"] or ds.height != annotation["number_of_lines"]:
            raise ValueError("TIFF/annotation dimensions or band count mismatch")
        source = ds.read(1, window=window)
        profile = {"driver": ds.driver, "width": ds.width, "height": ds.height,
                   "count": ds.count, "dtype": ds.dtypes[0], "nodata": ds.nodata,
                   "block_shape": list(ds.block_shapes[0])}
    if not np.iscomplexobj(source):
        raise ValueError("Expected complex Sentinel-1 SLC samples")
    coords = np.vstack(((lines-row0).ravel(), (samples-col0).ravel()))
    real = map_coordinates(source.real.astype(float), coords, order=order, mode="nearest")
    imag = map_coordinates(source.imag.astype(float), coords, order=order, mode="nearest")
    data = (real + 1j*imag).reshape(xx.shape)
    support = {"source_window_col_row_width_height": [col0, row0, col1-col0, row1-row0],
               "sample_min_max": [float(samples.min()), float(samples.max())],
               "line_min_max": [float(lines.min()), float(lines.max())],
               "all_contributing_samples_valid": True, "burst_index": burst_index,
               "interpolation_order": order, "tiff_profile": profile,
               "real_std": float(data.real.std()), "imag_std": float(data.imag.std())}
    return data, lines, samples, valid, support


def detrend2d(image, x, y, kind="plane"):
    z = np.asarray(image, float)
    xn = (x-x.mean()) / max(np.ptp(x), 1)
    yn = (y-y.mean()) / max(np.ptp(y), 1)
    cols = [np.ones(z.size), xn.ravel(), yn.ravel()]
    if kind == "quadratic":
        cols += [(xn*xn).ravel(), (xn*yn).ravel(), (yn*yn).ravel()]
    elif kind != "plane":
        raise ValueError("detrend must be plane or quadratic")
    a = np.column_stack(cols)
    finite = np.isfinite(z.ravel())
    beta = np.linalg.lstsq(a[finite], z.ravel()[finite], rcond=None)[0]
    return z - (a @ beta).reshape(z.shape)


def taper2d(shape, kind="hann"):
    if kind == "hann":
        wy, wx = np.hanning(shape[0]), np.hanning(shape[1])
    elif kind == "tukey_alpha_0.25":
        wy, wx = tukey(shape[0], .25), tukey(shape[1], .25)
    else:
        raise ValueError("unknown taper")
    return wy[:, None] * wx[None, :]


def _quadratic_offset(a, b, c):
    denom = a - 2*b + c
    if not np.isfinite(denom) or denom >= 0 or abs(denom) < 1e-15:
        return 0.0
    return float(np.clip(.5*(a-c)/denom, -.5, .5))


def conjugate_average(power, kx, ky):
    # Exact DFT-index involution.  The even-length Nyquist bin is its own
    # conjugate; nearest-coordinate matching gets this edge case wrong because
    # +Nyquist is not present in fftfreq.
    ix = (2*(len(kx)//2)-np.arange(len(kx))) % len(kx)
    iy = (2*(len(ky)//2)-np.arange(len(ky))) % len(ky)
    return .5 * (power + power[np.ix_(iy, ix)])


def spatial_spectrum(image, xx, yy, *, detrend="plane", taper="hann", padding=2,
                     exclusion_bins=2, basis_en=None):
    """Unconstrained SAR-only global peak; no expected wave or depth inputs."""
    z = detrend2d(image, xx, yy, detrend) * taper2d(image.shape, taper)
    ny, nx = z.shape
    nfy, nfx = padding*ny, padding*nx
    power = np.abs(np.fft.fftshift(np.fft.fft2(z, s=(nfy, nfx))))**2
    dx = float(np.median(np.diff(xx[0]))); dy = float(np.median(np.diff(yy[:, 0])))
    kx = 2*np.pi*np.fft.fftshift(np.fft.fftfreq(nfx, dx))
    ky = 2*np.pi*np.fft.fftshift(np.fft.fftfreq(nfy, dy))
    power = conjugate_average(power, kx, ky)
    cy, cx = nfy//2, nfx//2
    mask = np.ones(power.shape, bool)
    radius = exclusion_bins * padding
    mask[cy-radius:cy+radius+1, cx-radius:cx+radius+1] = False
    # Keep one member of each conjugate pair for an unambiguous reported sign.
    canonical = (kx[None, :] > 0) | ((np.abs(kx[None, :]) < 1e-14) & (ky[:, None] > 0))
    search = np.where(mask & canonical, power, -np.inf)
    iy, ix = np.unravel_index(np.argmax(search), search.shape)
    logp = np.log(np.maximum(power, np.finfo(float).tiny))
    ox = _quadratic_offset(logp[iy, ix-1], logp[iy, ix], logp[iy, ix+1]) if 0 < ix < nfx-1 else 0
    oy = _quadratic_offset(logp[iy-1, ix], logp[iy, ix], logp[iy+1, ix]) if 0 < iy < nfy-1 else 0
    kxf = float(kx[ix] + ox*(kx[1]-kx[0])); kyf = float(ky[iy] + oy*(ky[1]-ky[0]))
    basis = np.eye(2) if basis_en is None else np.asarray(basis_en, float)
    ken = np.linalg.solve(basis.T, np.asarray([kxf, kyf]))
    kmag = float(np.linalg.norm(ken)); bearing = math.degrees(math.atan2(ken[0], ken[1])) % 360
    peak = float(power[iy, ix])
    # Half-power connected component around the selected peak.
    above = power >= peak/2
    seen={(iy,ix)}; stack=[(iy,ix)]
    while stack:
        a,b=stack.pop()
        for da,db in ((-1,0),(1,0),(0,-1),(0,1)):
            q=(a+da,b+db)
            if 0<=q[0]<nfy and 0<=q[1]<nfx and q not in seen and above[q]:
                seen.add(q); stack.append(q)
    radial=[]
    for a,b in seen:
        q=np.linalg.solve(basis.T,np.asarray([kx[b],ky[a]])); radial.append(np.linalg.norm(q))
    fwhm=float(max(radial)-min(radial)) if radial else float('nan')
    KX,KY=np.meshgrid(kx,ky); kr=np.sqrt(KX*KX+KY*KY)
    dk=max(abs(kx[1]-kx[0]),abs(ky[1]-ky[0]))
    ann=(np.abs(kr-math.hypot(kxf,kyf))<=dk) & mask
    for a,b in seen: ann[a,b]=False
    background=float(np.median(power[ann])) if np.any(ann) else float(np.median(power[mask]))
    return {"power":power,"kx":kx,"ky":ky,"selected_index":[int(iy),int(ix)],
            "discrete_k_frf_rad_m":[float(kx[ix]),float(ky[iy])],
            "interpolated_k_frf_rad_m":[kxf,kyf],"k_east_rad_m":float(ken[0]),
            "k_north_rad_m":float(ken[1]),"k_magnitude_rad_m":kmag,
            "wavelength_m":float(2*np.pi/kmag),"bearing_toward_deg":bearing,
            "axial_bearing_deg":bearing%180,"peak_power":peak,
            "lobe_to_annular_median":peak/background if background>0 else float('inf'),
            "half_power_radial_width_rad_m":fwhm,"conjugate_closure_relative":float(np.max(np.abs(power-conjugate_average(power,kx,ky)))/peak),
            "zero_padding_factor":padding,"padding_role":"interpolation only",
            "bin_step_unpadded_rad_m":[float(2*np.pi/(nx*dx)),float(2*np.pi/(ny*dy))],
            "bin_step_padded_rad_m":[float(kx[1]-kx[0]),float(ky[1]-ky[0])],
            "physical_window_m":[float(nx*dx),float(ny*dy)],"detrend":detrend,"taper":taper}


def axial_difference(a, b):
    return abs((float(a)-float(b)+90) % 180 - 90)


def invert_dispersion(k, omega_absolute, current_along_k=0.0, g=9.80665):
    intrinsic = float(omega_absolute) - float(k)*float(current_along_k)
    ratio = intrinsic**2/(g*float(k))
    if not 0 < ratio < 1:
        return {"depth_m": np.nan, "intrinsic_omega_rad_s": intrinsic,
                "status": "no_finite_positive_depth"}
    return {"depth_m": float(np.arctanh(ratio)/float(k)),
            "intrinsic_omega_rad_s": intrinsic, "status": "finite"}
