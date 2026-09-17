"""Verified Block30 scalar parser plus strict DAP2 multidimensional extension."""
from __future__ import annotations
import math
import re
from datetime import datetime, timezone
import numpy as np
from run_block30_frf_conditions import parse_ascii_vector  # one shared verified parser


def utc(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Explicit timezone required; UTC or numeric offset")
    return parsed.astimezone(timezone.utc)


def cf_times(values, units):
    match = re.match(r"(seconds|minutes|hours|days) since (.+)", units)
    if not match:
        raise ValueError("Unsupported CF time units")
    epoch = match[2].strip()
    # CF metadata supplies its UTC epoch; this rule is NOT used for acquisition inputs.
    if not re.search(r"Z$|[+-]\d\d:\d\d$", epoch):
        epoch += "+00:00"
    scale = {"seconds": 1, "minutes": 60, "hours": 3600, "days": 86400}[match[1]]
    return utc(epoch).timestamp() + np.asarray(values, float) * scale


def das_attributes(text):
    result = {}
    for match in re.finditer(r"\b(\w+)\s*\{([^{}]*(?:DODS\s*\{[^{}]*\}[^{}]*)?)\}", text, re.S):
        attrs = {}
        for attr in re.finditer(r'(?:String|Float\d+|[UI]?Int\d+|Byte)\s+(\w+)\s+("(?:[^"\\]|\\.)*"|[^;]+);', match[2], re.S):
            value = attr[2].strip()
            if value.startswith('"'):
                attrs[attr[1]] = value[1:-1].replace('\\"', '"')
            else:
                try:
                    nums = [float(v.strip()) for v in value.split(",")]
                    nums = [n if math.isfinite(n) else str(n) for n in nums]
                    attrs[attr[1]] = nums[0] if len(nums) == 1 else nums
                except ValueError:
                    attrs[attr[1]] = value
        result[match[1]] = attrs
    return result


def dds_shapes(text):
    return {m[1]: [int(n) for n in re.findall(r"=\s*(\d+)\]", m[2])]
            for m in re.finditer(r"(?:Float\d+|[UI]?Int\d+|Byte)\s+(\w+)\s*((?:\[[^\]]+\])*)\s*;", text)}


def ascii_arrays(text):
    """DAP2 .ascii numeric arrays: strip row indices, enforce declared shape.

    Vectors delegate to the Block30 parser. Indexed ND rows do not delegate:
    [i][j], prefixes are indices, never measured numeric values.
    """
    if not re.search(r"^-{10,}\s*$", text, re.M):
        raise ValueError("Not DAP2 ASCII data")
    body = re.split(r"^-{10,}\s*$", text, flags=re.M)[1]
    headings = list(re.finditer(r"^\s*([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)((?:\[\d+\])*)\s*$", body, re.M))
    result = {}
    for j, heading in enumerate(headings):
        name = heading[1]
        dims = tuple(int(x) for x in re.findall(r"\[(\d+)\]", heading[2]))
        fragment = body[heading.end():headings[j+1].start() if j+1 < len(headings) else len(body)]
        if len(dims) <= 1 and "." not in name:
            values = parse_ascii_vector("--------------------\n" + heading[0] + fragment, name)
        else:
            values = []
            for line in fragment.splitlines():
                line = re.sub(r"^\s*(?:\[\d+\])+\s*,?\s*", "", line)
                if not line.strip():
                    continue
                for token in line.split(","):
                    if token.strip():
                        try:
                            values.append(float(token))
                        except ValueError as exc:
                            raise ValueError(f"Malformed numeric DAP row for {name}") from exc
        if dims and len(values) != math.prod(dims):
            raise ValueError(f"Shape mismatch for {name}: {len(values)} vs {dims}")
        array = np.asarray(values, float).reshape(dims or ())
        result[name] = array
    if not result:
        raise ValueError("Empty DAP payload")
    # DAP2 scalars are inline ("latitude, 36.2"), unlike array headings.
    for scalar in re.finditer(r"^\s*([A-Za-z_]\w*)\s*,\s*([^,\n]+)\s*$",body,re.M):
        try:
            result[scalar[1]] = np.asarray(float(scalar[2]))
        except ValueError:
            continue
    # DAP2 GRID returns array.array plus array.dimension maps. Validate, then
    # canonicalize them; otherwise a retrieved spectrum would be invisible.
    canonical = {}
    for name,arr in result.items():
        key = name.split(".")[-1]
        if key in canonical and (canonical[key].shape != arr.shape or not np.allclose(canonical[key],arr,equal_nan=True)):
            raise ValueError(f"Conflicting DAP GRID coordinate {key}")
        canonical[key]=arr
    return canonical


def mask_values(values, attrs):
    arr = np.asarray(values, float)
    good = np.isfinite(arr)
    for key in ("_FillValue", "missing_value"):
        for fill in np.atleast_1d(attrs.get(key, [])):
            try:
                good &= arr != float(fill)
            except (TypeError, ValueError):
                pass
    if "valid_min" in attrs:
        good &= arr >= float(attrs["valid_min"])
    if "valid_max" in attrs:
        good &= arr <= float(attrs["valid_max"])
    if "valid_range" in attrs:
        good &= (arr >= attrs["valid_range"][0]) & (arr <= attrs["valid_range"][1])
    return good


def qc_pass(values, attrs, allowed=(1,)):
    return mask_values(values, attrs) & np.isin(values, allowed)


def toward(direction, convention):
    if convention == "from_true_north":
        return (np.asarray(direction) + 180) % 360
    if convention == "toward_true_north":
        return np.asarray(direction) % 360
    raise ValueError("Unverified direction convention")


def circular_mean(degrees, weights=None):
    angles = np.deg2rad(degrees)
    z = np.average(np.exp(1j*angles), weights=weights)
    return None if abs(z) < 1e-12 else float(np.angle(z, deg=True) % 360)


def associate(times, target, eligible, tolerance_seconds, intervals=None):
    times = np.asarray(times, float)
    indices = np.flatnonzero(np.isfinite(times) & np.asarray(eligible, bool))
    before = indices[times[indices] <= target]
    after = indices[times[indices] >= target]
    nearest = min(indices, key=lambda i: abs(times[i]-target)) if len(indices) else None
    result = {"previous": int(before[np.argmax(times[before])]) if len(before) else None,
              "next": int(after[np.argmin(times[after])]) if len(after) else None,
              "nearest": int(nearest) if nearest is not None else None,
              "tolerance_seconds": tolerance_seconds, "interpolation": "none"}
    if nearest is not None:
        delta = float(times[nearest]-target)
        result.update(offset_seconds=delta, within_tolerance=abs(delta) <= tolerance_seconds)
        if intervals is not None:
            lo, hi = intervals[nearest]
            result["interval_distance_seconds"] = max(lo-target, target-hi, 0.)
            result["observation_interval"] = [float(lo), float(hi)]
        else:
            result["interval_distance_seconds"] = None
    return result


def spectral_summary(f, energy, valid, widths=None):
    """Rectangular bin integration; never bridge missing bins."""
    f, energy, valid = np.asarray(f), np.asarray(energy), np.asarray(valid, bool)
    if f.ndim != 1 or len(f) < 2 or len(f) != len(energy) or np.any(np.diff(f) <= 0):
        raise ValueError("Invalid spectral grid")
    origin = "provided"
    if widths is None:
        edges = np.r_[f[0]-(f[1]-f[0])/2, (f[:-1]+f[1:])/2, f[-1]+(f[-1]-f[-2])/2]
        widths = np.diff(edges)
        origin = "reconstructed_midpoint_edges"
    widths = np.asarray(widths)
    if widths.shape != f.shape or np.any(widths <= 0):
        raise ValueError("Invalid bin widths")
    good = valid & np.isfinite(energy) & (energy >= 0) & (f > 0)
    m0 = float(np.sum(energy[good]*widths[good]))
    m1 = float(np.sum(energy[good]*widths[good]*f[good]))
    m2 = float(np.sum(energy[good]*widths[good]*f[good]**2))
    peak = int(np.argmax(np.where(good, energy, -np.inf))) if np.any(good) else None
    return {"formula": "mn=sum_valid(E(f)*df*f**n); Hm0=4sqrt(m0); Tm01=m0/m1; Tm02=sqrt(m0/m2)",
            "bin_width_origin": origin, "widths_hz": widths.tolist(),
            "valid_band_hz": [float(f[good].min()),float(f[good].max())] if np.any(good) else None,
            "valid_bin_fraction": float(np.mean(good)), "missing_bin_indices": np.flatnonzero(~good).tolist(),
            "m0_m2": m0, "Hm0_m": 4*math.sqrt(m0),
            "Tm01_s": m0/m1 if m1 else None, "Tm02_s": math.sqrt(m0/m2) if m2 else None,
            "Tp_bin_s": 1/float(f[peak]) if peak is not None else None,
            "peak_bin": peak, "partial_integral": not bool(np.all(good)),
            "swell_partitions": "not inferred", "directional_reconstruction": "none"}
