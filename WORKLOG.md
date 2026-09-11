# Work log

All paths below are under `D:\Dati Tesi\Umbra` unless an input is explicitly
identified as read-only. Times use Europe/Rome.

## 2026-08-29 — checkpoint block 1

### 15:18–15:22 — initial state

- Printed current directory, Python candidates, workspace TEMP/TMP targets,
  D: capacity, top-level tree, and recursive initial inventory.
- Input: workspace filesystem. Output: console only.
- Result: root confirmed as `D:\Dati Tesi\Umbra`; 652.294 GiB free initially.
- Error: the first PowerShell inventory command had an invalid `Sort-Object`
  parameter list and stopped at parse time. Corrected and rerun; no filesystem
  operation occurred in the failed command.
- Verified CPHD size by file metadata only: 140,554,224,768 bytes, exact match.
- Confirmed no local SICD/NITF.

### 15:22–15:27 — supplied-code audit and CPHD lightweight inspection

- Read `download_vandenberg_sicd.bat`, `README_Vandenberg_SICD.md`, and
  `sicd_subaperture.py` completely. Originals were not modified.
- Read 64 KiB from the CPHD start; parsed the 308-byte ASCII header and the
  20,373-byte XML block at byte 1,024.
- Memory-mapped the 62,387,424-byte PVP block and scanned selected PVP fields.
  The 140,491,169,280-byte signal block was not read.
- Error: an initial NumPy `memmap(..., strides=...)` call was rejected before
  producing results. Replaced with a structured 376-byte dtype and reran.
- Result: CPHD/PVP timing, cadence, polarization, frequency, SRP, side of track,
  geometry, and ground-track bearing verified.

### 15:27–15:31 — remote asset preflight, no full download

- Queried the official Umbra public data catalog, STAC JSON, S3 listing, and HTTP
  headers in read-only mode.
- Error: sandbox proxy blocked the first local curl attempt. Reran the read-only
  requests with approved network access.
- Confirmed public SICD key and Content-Length 11,478,596,733 bytes.
- Found and documented the difference between public key time `18-55-44` and
  internal STAC production asset time `18-55-33`.
- Attempted the internal STAC asset name in the public prefix; S3 returned 404.
  The folder listing then established the exact public key.

### 15:31–15:37 — workspace setup and environment

- Copied the read-only uploaded task from C: to `TASK_SPEC.md`; SHA-256 matched.
- Created `code`, `tests`, `Vandenberg/metadata`, `Vandenberg/roi`,
  `Vandenberg/results/diagnostics`, `_tmp`, and `_cache/pip` under D:.
- Created `.venv` under D: with Python 3.11.15.
- Error: the first pip call was blocked by sandbox networking. Reran with
  approved access and installed all packages only into `.venv`, with TEMP/TMP
  and pip cache on D:.
- Output and versions are recorded in `ENVIRONMENT.md`.

### 15:37–15:43 — SICD metadata by HTTP ranges

- Downloaded only four temporary fragments under `_tmp`: first NITF MiB, second
  image subheader (752 bytes), text segment (18,939 bytes), and SICD DES
  (31,848 bytes). Full SICD was not downloaded.
- Parsed NITF offsets with SarPy, extracted the 30,875-byte SICD XML, and checked
  it against the SICD 1.3.0 XSD.
- Ran SarPy semantic validation and inspected its validation source to separate
  a negative-chirp validator limitation from the genuine missing SVA WgtFunct.
- Added `code/cphd_inspect.py` and `code/sicd_metadata_from_ranges.py`.
- Generated `Vandenberg/metadata/CPHD_METADATA.json`, `CPHD_REPORT.md`,
  `SICD_METADATA.xml`, `SICD_METADATA.json`, `SICD_REPORT.md`, and
  `ASSET_PREFLIGHT.json`.
- Decision: use ImageFormation processed duration 18.068061721 s for SICD
  sub-aperture fractions; reserve the 22.540812513 s CPHD dwell for later CPHD
  slow-time mapping and refocusing.
- Decision: actual split axis is Col/NumPy axis 1; actual forward transform is
  `fft_sicd`, resolving to NumPy FFT because Col.Sgn = -1.

## Filesystem compliance

No file was created, modified, deleted, installed, or downloaded outside
`D:\Dati Tesi\Umbra`. The uploaded attachment and installed base interpreters on
C: were read-only inputs. Original CPHD, GEC, and supplied scripts were not
modified.

## 2026-08-29 — checkpoint block 2

### Metadata-aware core

- Added `code/umbra_sar/subaperture.py` with explicit SICD axis/Sgn handling,
  distinct SICD/CPHD duration fields, processed-support derivation, centered and
  tiled/overlap planning, rectangular and Tukey windows, normalization/ENBW,
  complex filtering, and JSON-ready provenance.
- Added `code/umbra_sar/cross_spectrum.py` with explicit
  `F_secondary * conj(F_reference)` ordering.
- SVA without WgtFunct is preserved as a warning and does not block the core.
- Added metadata-only `code/plan_subapertures.py` and generated the future 6 s
  plan without reading SICD pixels.

### Synthetic tests

- Added five test groups under `tests/test_subaperture.py`: FFT/IFFT,
  split/recombine, axis, band location, and cross-spectrum phase.
- First run: 17/18 passed. The sole failure was a manually hardcoded expected
  center time that ignored integer-bin quantization. Replaced it with an
  expectation derived from realized bin width and symmetry; processing code did
  not change.
- Added a nineteenth test comparing the new transform directly with SarPy
  `fft_sicd` using actual metadata and synthetic pixels.
- Final run: 19/19 passed.
- A placeholder import accidentally remained while initially scaffolding
  `tests/generate_test_report.py`; it was detected before execution and replaced
  immediately. It produced no output and affected no test result.
- Generated `tests/TEST_METRICS.json` and `tests/TEST_REPORT.md`; all independent
  threshold checks pass.

### Stop condition

- Confirmed the full SICD remains absent.
- No real SAR image pixels or ocean products were processed.
- Block 2 stopped at the requested test report before scientific interpretation.

## 2026-08-29 — checkpoint block 3

### Verified-download setup and reproducible ROI selection

- Added a resumable downloader that verifies remote Content-Length and ETag
  before transfer and deliberately retains a `.part` suffix until local
  multipart-ETag verification passes.
- Started the only authorized large download: the 11,478,596,733-byte public
  SICD into `Vandenberg`; no other dataset was downloaded.
- Read the existing GEC only as a geographic locator. Generated a georeferenced
  overview and fixed nearshore, offshore, and land-control polygons in
  `Vandenberg/roi/ROIS.json`.
- Each ROI is approximately 0.69 km square. The two ocean polygons are clear of
  land in the GEC overlay; the land polygon contains persistent infrastructure.
- Added `select_vandenberg_rois.py`; the JSON records GEC pixels, lat/lon on the
  shared reference plane, SICD bounds, corner coordinates, and local EN ground
  Jacobians.

### CPHD PVP Doppler/slow-time mapping

- Added and ran `cphd_doppler_time_mapping.py`. It read CPHD header/XML/PVP only;
  the CPHD signal block was not read.
- Derived `k_ECF(t)=(2*f_proc/c)*unit(SRPPos-TxPos)` and projected it onto the
  actual SICD Grid Row/Col unit vectors.
- `k_col(t)` is strictly decreasing. This establishes look 1 as late, look 2 as
  central, and look 3 as early, correcting the direction of the metadata-only
  nominal time labels without changing the fixed FFT bands.
- The interpolated Row coordinate reproduces SICD `Row.KCtr` to about
  1.6e-11 cycles/m; CPHD PVP and SICD ARP-polynomial Col coordinates agree to
  about 4.4e-9 cycles/m RMS over the processed interval.
- Generated `CPHD_DOPPLER_TIME_MAPPING.json`, its diagnostic plot, and an exact
  Doppler-window plot. No cross phase was converted to period.

### Block-3 processing implementation and method validation

- Added chunked full-azimuth sub-look formation. For every selected range row,
  all 107,800 SICD columns are transformed before the ROI columns are cropped.
- Added physical EN wave-spectrum peak measurement, explicit wavevector versus
  perpendicular crest orientation, three-look matching thresholds, conditional
  intensity cross-spectra, phase closure, and land phase-correlation/ramp checks.
- Primary-method check: Li et al. (2019), JGR Oceans,
  DOI 10.1029/2018JC014638, section 2.2.1 explicitly forms sub-look intensity
  images after splitting the SLC Doppler spectrum and then computes image
  cross-spectra. The code follows this choice while retaining complex64 masters.
- Added two synthetic regression tests for physical wavevector recovery and
  signed phase-correlation/ramp recovery. Current suite: 21/21 passed.
- Guardrails remain active: no dwell sweep, no depth inversion, no declaration
  of a SAR wave period.

### Block-3 completion

- Finalized the SICD only after exact local verification: 11,478,596,733 bytes,
  multipart ETag `f06d503551fb567303477152aee18652-219`, and SHA-256
  `56605c95701a5dd081c5faa7b1a39304a3907ed01f6eb576ea19ce4ea80e585d`.
  NITF length/segments, stitched SarPy shape and sampled complex pixels, XML
  equality, and XSD validation passed. The known downchirp-validator and
  SVA-without-WgtFunct messages remain documented and nonblocking.
- The first GEC-projected ocean centers inherited a constant-HAE shoreline
  displacement. Those products were preserved under `*_initial_gec_roi`, not
  deleted. Final ocean ROI centers were selected reproducibly on the full SICD
  intensity and are entirely ocean; all final spectra were recomputed.
- Formed all three complex64 sub-looks by transforming every one of the 107,800
  azimuth samples for each requested range row and cropping only after inverse
  transformation. The manifest records array hashes and zero nonfinite input
  samples.
- Nearshore peak: robust across looks, mean wavelength 130.60 m, wavevector
  bearing 79.84 degrees mod 180, crest bearing 169.84 degrees, and local
  smoothed phase-closure residual 0.0409 rad. Offshore peak: robust but
  marginal in wavelength-span threshold, mean 45.47 m; cross-look coherence is
  poor and its smoothed phase closure is 1.155 rad, so it is not assigned a
  physical temporal interpretation.
- Raw land-intensity phase correlation locked onto an outlier-driven false
  maximum near 98 m for pairs containing look 3. Log-intensity registration,
  direct overlap correlation, and multi-scale smoothing select zero shift.
  Robust pair displacements are 0.030, 0.034, and 0.131 m, with 0.067 m closure;
  ramp-removed resultants of 0.316--0.447 do not indicate one common phase ramp.
- Generated `CHECKPOINT_3.md` and `tests/TEST_REPORT_BLOCK3.md`; final synthetic
  regression result remains 21/21 passed.

## 2026-08-30 — Block 4 nearshore temporal phase

- Corrected the angle label: 105.848355722 degrees belongs to CPHD
  ReferenceGeometry at 11.075249663 s, whereas SICD SCPCOA.AzimAng is
  101.919310567 degrees at SCPTime 9.036361296 s. CPHD PVP interpolation
  reproduces both. The groundward LOS and tangent-projected positive Grid Row
  are 281.919 degrees; the local surface Grid-Row bearing is 281.179 degrees
  nearshore. Thus the prior 21.3-degree comparison used the correct local
  surface Jacobian and not the later CPHD reference angle.
- Planned 11 chronological 28,638-bin Tukey looks with PVP centers from
  3.242899 to 14.832257 s, 1.156--1.163 s spacing, 5.784--5.828 s effective
  spans, and 80% Doppler overlap. Chronological looks 1, 6, and 11 exactly reuse
  the three disjoint Block-3 bands, retained separately for future dispersion.
- Generated only the eight additional complex64 looks for nearshore and land.
  Every transformed row used all 107,800 SICD columns; no nonfinite samples
  were found and no small azimuth crop preceded Doppler decomposition.
- Froze a SAR-only result before accessing external observations. A fixed 5x5
  patch at the Block-3 nearshore peak gives omega=-0.350972206 rad/s,
  T_SAR=17.902230 s, fit-only 1-sigma period uncertainty 0.247103 s, RMSE
  0.053226 rad, and R-squared 0.998288. Adjacent coherence is 0.973--0.992 and
  phase steps remain below 0.497 rad, justifying SAR-only temporal unwrap.
- Patch radii 1--5 give 17.884--17.940 s; adjacent-link accumulation gives
  18.825 s and the noisier center bin 20.384 s. These are retained as method
  sensitivity rather than folded into the formal regression error. The
  conjugate spectral peak reverses omega and preserves the period numerically.
- At the same PVP centers, the land slope is 0.006054 +/- 0.016956 rad/s; its
  95% interval contains zero and R-squared is 0.0193. No land period is declared.
- Only after freezing the SAR result, downloaded the 984,228-byte official
  NOAA/NDBC 2025 file for station 46218 Harvest (CDIP 071). The observation at
  18:56 UTC, 15.7 s after SICD midpoint and 17.89 km from the ROI, reports DPD
  13.33 s, APD 7.31 s, Hs 2.02 m and MWD 252 degrees from. The SAR period was
  not retuned; its undirected direction axis is within 7.84 degrees of the buoy.
- Added the Block-4 fixed-patch temporal sign/unwrap/rate regression test. Final
  suite: 22/22 passed. Stopped at CHECKPOINT_4 with no dwell sweep and no
  bathymetric inversion.

## 2026-08-31 — Block 5 nearshore physical identification

- Froze the unmodified Block-4 SAR-only result at SHA-256
  `c399af008e2159ede9b6e27b8bf99dffdd17b7f808aa263ea569d20438df8fcd`:
  omega=-0.350972205517 rad/s and T_SAR=17.902230457045 s. External data did
  not enter its fit, unwrap, or uncertainty.
- Downloaded the complete official NDBC 46218 directional spectral aggregate:
  153,486,944 bytes, SHA-256
  `eb296c36049de144043c1a8b39a59df1ebeb50453541d23a0a784badcee0d20d`.
  The closest spectral record is 19:00 UTC (+255.726 s) and includes all 64
  frequencies plus C11, alpha1, alpha2, r1, and r2.
- The 0.055-Hz bin (18.18 s) has C11=0.132 m2/Hz, propagation-to 80 degrees,
  and r1=0.29. The 0.075-Hz bin (13.33 s) is the robust maximum with
  C11=4.400 m2/Hz, propagation-to 72 degrees, and r1=0.89. The long-bin
  density is only 3% of the peak and is not a separate spectral maximum.
- The integrated spectrum gives Hm0=1.987 m. Sub-bin peaks from 0.065 to
  0.101 Hz merge into one 0.075-Hz maximum under 0.75-bin smoothing; a
  shorter-period secondary energy band is present but no independent 17.9-s
  component is resolved.
- The finite-depth forward diagnostic for lambda=130.603 m requires 5.556 m
  at 17.902 s or 10.627 m at 13.33 s. Coarse 30-arc-second ETOPO gives 3.227 m
  at the mixed shoreline cell and 2.5--36.0 m in nearby water cells, so it
  cannot select either case and was not used as a bathymetric inversion.
- Audited Engen-Johnsen and Sentinel-1 OSW Eq. (34). The quasi-linear phase
  contains both |T(k)|2 S(k) exp(-i omega t) and |T(-k)|2 S(-k) exp(+i omega t),
  while OSW explicitly removes a complex nonlinear term. A stationary
  bidirectional mixture cannot reproduce the 13.33-s hypothesis over the
  actual 11.589-s lag range without an additional phase-rate contribution.
- Ran a moderate SAR-only sensitivity, not a dwell sweep: 5.5/6.0/6.5-s
  widths at nine common centers, 80/60/40% overlap subsampling, six ROI crops,
  and nine spectral-patch variants. All 24 fits remain negative with R-squared
  >=0.997; the total slope range is -0.367782 to -0.341030 rad/s. The frozen
  slope is therefore robust to the tested processing choices.
- Added nine Block-5 tests for physical equations and artifact guardrails.
  Final suite: 31/31 passed. CHECKPOINT_5 selects conclusion 2: the SAR spatial
  peak most likely corresponds to the dominant approximately 13.3-s buoy
  system, while its inter-look phase rate includes an unresolved physical or
  processing bias. No 5--16-s sweep and no depth inversion were performed.
