# Block36 protocol — authenticated Sentinel-1 IW annotation preflight

Frozen before any Block36 HTTP request. Block36 is the first free identifier.
It does not reopen the Block35 ranking or query the 11 October alternative.

## Objective and boundaries

Verify the primary Block35 ROI against VV IW1/IW2/IW3 annotation metadata,
valid burst samples and local geolocation. Prepare a spatial-intensity trial in
which SAR supplies `k` while the independent FRF spectra constrain possible
external `omega`. This is not temporal SAR validation, image formation or an
inversion. Spotlight sub-apertures, TOPS overlaps and combinations remain open
project alternatives; this block adopts none of them for the thesis method.

No measurement TIFF, full SAFE, radar pixels, alternate scene, FRF request,
real inversion or parameter tuning is permitted. Block35 payloads/results are
read-only inputs. A geometry-blocking ROI variant may be declared only before
pixel analysis and only with a documented support reason.

## Authentication and network tranche

New independent tranche: 40 HTTP transactions, 50 MiB total, 10 MiB per
response, TLS verified, no implicit reset, zero retries. Redirects/errors count.
The ledger exists before the first request. Verified Block35 public Nodes and
documentation may be imported without charging this tranche.

The primary local setup is a Git-ignored root `.env` containing
`CDSE_USERNAME` and `CDSE_PASSWORD`; `.env.example` contains empty fields only.
`CDSE_ACCESS_TOKEN` remains an environment/file alternative and takes
precedence. The official CDSE password grant is sent as form data to the
Keycloak token endpoint with `client_id=cdse-public`. A refresh token, when
returned, and access-token expiry are handled only in process memory. Sources:
[CDSE Token Generation](https://documentation.dataspace.copernicus.eu/APIs/Token.html)
and [OData product download](https://documentation.dataspace.copernicus.eu/APIs/OData.html#product-download).

Authentication POSTs, error responses and refreshes consume the same tranche.
There are at most three authentication requests and one metadata retry after a
401. Request forms and identity-response bodies are never cached, logged or
printed. Redirects are refused. If the first password grant is rejected, an
MFA/TOTP code is requested once with hidden terminal input and sent using the
official `totp` parameter; it is never persisted. MFA is not bypassed.

If neither a credential pair nor a direct token is configured: initialize the
zero-use tranche, complete/test the offline pipeline and emit `BLOCKED`. Do not
repeat the known anonymous 401.

Allowed product content: `manifest.safe`, the three VV measurement annotation
XMLs and, after identifying the pertinent subswath, its calibration and noise
annotation XML. Public node listings are allowed. Measurement TIFF/PDF/preview
content and a full product `$value` are forbidden. Expected node name, declared
ContentLength <=10 MiB, XML root/identity and SHA256 are checked before use.

## Geometry/support rules

Array order is `[azimuth line, slant-range sample]`. Invalid values (`-1`) in
`firstValidSample/lastValidSample` form no observations. ROI containment is
reported independently for catalogue footprint, annotation subswath convex
geolocation support and per-burst valid samples. Crossing a burst join is not
silently mosaicked and overlap is not duplicated. Prefer a single valid burst.

Local image-to-ground Jacobian is evaluated at ROI center from the annotation
geolocation grid, with variation at ROI boundary. Image angular wavenumber is
ordered `[q_sample, q_line]` in rad/pixel and transforms to local ENU horizontal
`[k_east,k_north]` by `J^{-T}`. FFT convention is NumPy forward negative
exponent, `fftshift(fftfreq)`, cycles/pixel converted by `2*pi`; raster bearing
and propagation bearings are clockwise from true north, axial comparisons are
modulo 180. FRF `from` becomes `toward=(from+180)%360`; it never rotates a SAR
peak. Footprint-edge bearing is not local range.

Slant-range/azimuth pixel spacing from annotation, geolocated ground spacing
and effective resolution are distinct. Missing resolution is not replaced by
spacing. Zero padding interpolates the sampled spectrum only.

## First spatial-trial plan (no pixels read here)

1. Open only VV measurement for the verified subswath/burst; apply the valid
   sample mask before statistics. Never interpret invalid pixels as zero sea.
2. Form intensity `|SLC|^2`. Apply documented beta/sigma calibration LUT only
   after verifying its interpolation/definition; preserve an uncalibrated
   diagnostic. Apply noise subtraction only with the matching noise XML, in
   the documented domain, clipping is flagged rather than hidden.
3. Map pixels to local metric coordinates with the verified Jacobian or a
   quantified higher-order mapping if its ROI variation is material.
4. Test predeclared metric windows 300x300, 400x300 and 500x300 m only when
   entirely within one valid burst and supported by the survey. If a size does
   not fit it is unavailable, not resized to match an expected wavelength.
5. Plane detrend is primary; quadratic is a labelled sensitivity diagnostic.
   Hann and Tukey(alpha=.25) are the predeclared windows. Record coherent gain,
   ENBW and full 2-D response. No expected-wave bandpass.
6. Compute 2-D FFT of real intensity. Treat conjugate peaks as one axial pair;
   retain both coordinates/powers. Estimate peak/lobe locally with discrete
   bin, zero-padded interpolation (factor 2) and a fitted estimator kept
   separate. Report bin spacing, window response width, physical lobe width and
   estimator/variant uncertainty separately.
7. Transform `q` through `J^{-T}`; report `|k|`, wavelength and geographic
   propagation-axis candidates. Test stability over the available fixed
   window/detrend/windowing variants. No minimum-cycle/dwell/phase gate and no
   universal `L/W` accuracy floor.
8. Only later compare stable SAR structures with the full FRF band/directions.
   Valid outcomes include “association not identifiable”. Any inversion is a
   separate stage conditional on external omega, current uncertainty and an
   independent survey comparison; no parameter is adjusted for agreement.
