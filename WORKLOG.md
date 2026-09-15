# Work log

All paths below are under `D:\Dati Tesi\Umbra` unless an input is explicitly
identified as read-only. Times use Europe/Rome.

## 2026-09-14 — Block16A completed: metadata-only validation-scene selector

- Added the configurable Block16A selector, dedicated pure-function library,
  33 focused offline tests, frozen protocol/configuration, immutable catalog
  snapshots, provenance tables, six reviewed figures and a delivery manifest.
- Canonical snapshot `20260913T231747Z` contains 94,929 listed objects, 12,542
  STAC processings and 10,140 unique physical acquisitions. Deduplication by
  `collect_id` identifies 2,402 extra processing rows; 45 acquisitions have
  anomalous date/duration flags and remain audit-visible but excluded.
- The gates find 5,438 preferred records with both CPHD and SICD, 215
  preliminary marine ROIs, 4 complete measured directional spectra, 27/22
  acquisitions above the minimum/preferred observable-cycle thresholds, and
  three passing the joint temporal/preliminary-spatial/directional geometry
  screen. Five finalists pass limited CPHD/SICD byte-range association audits.
- Final categories are A=0, B=1, C=33, D=10,106, E=0. No primary measured
  validation scene exists. The sole B alternative is
  `2024-10-22-22-04-46_UMBRA-09`; its 4.5 s period is explicitly a provisional
  model mean-period proxy, not a measured peak period, and its nearest active
  buoy is 119.6 km away. Thresholds were not relaxed.
- Corrected the reference classifier so an active station beyond the frozen
  50 km radius is not labelled a nearby buoy; added a regression test. Full
  project suite: 168 passed in 7.31 s, zero failed/skipped, using the dedicated
  `.venv-umbra-thesis` interpreter.
- No complete CPHD/SICD/SIDD/GEC, CPHD signal array or image pixels were read;
  metadata traffic was 51,135,325 bytes. Frozen Block8 and Block15K hashes are
  unchanged. No commit, push, scene processing or download was performed.

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

## 2026-09-11 — Block 15A operational audit (no scientific rerun)

- Audited current repository state, checkpoints 1–12, Block 11–14 code,
  manifests and lightweight results. Initial branch main, commit
  d5fab7b4c49bb9c5d4a0a8dbfdb0b2dc316a2fdf, clean worktree.
- Verified local BP12/BP13 NPY headers: 32x288x130 and 32x600x130
  complex64; verified SICD header and source file sizes without radar pixel
  reads or new integral hashes. A read-only TxTime PVP check reproduces all
  32 look counts and mean times (maximum difference 7.82e-14 s).
- Confirmed degenerate single-realization coherence in the first Block12
  analysis; subsequent 3x3-smoothed coherence is magnitude, not MSC, and
  does not update previous outputs. Confirmed Block13 dem_depth_m is a
  parametric edge-depth/gradient profile, not local raster sampling.
- Block14 controlled_for_wavelength/model_comparison and added
  interpretations have no reconstructed generator in available local
  source/history. Documented shared-pair dependence and non-equivalence
  of raw-bin and patch phase estimators.
- Current prescribed environment: .venv-umbra-thesis, Python 3.13.9,
  SarPy 2.0.1. Existing suite rerun with bytecode/cache writes disabled:
  57 passed in 5.61 s; 0 failed, 0 skipped. No automatic CPHD
  backprojection or Block12–14 selection coverage. rasterio/pyproj absent;
  no installation or alternate environment used.
- Added results/analysis_block15/BLOCK15A_AUDIT.md and
  BLOCK15A_INPUT_INVENTORY.json under Vandenberg. Proposed BP12 as first
  controlled-estimator input on provenance/support grounds, not external
  agreement. Block15B is proposed only, not started.
- Frozen results and T_SAR=17.902230457 s unchanged. No radar download,
  look formation, dwell sweep, inversion, production-code/test edits,
  commit or push.

## 2026-09-11 — Block 15B controlled BP12 estimator comparison

- Implemented code/umbra_sar/frequency_comparison.py, a scoped BP12 runner,
  a descriptive diagnostics script and 12 estimator-level synthetic tests.
  Historical production scripts and Block12 outputs remain unchanged.
- Commands used the prescribed .venv-umbra-thesis/Scripts/python.exe -B,
  with PYTHONDONTWRITEBYTECODE=1. First ran pytest
  tests/test_frequency_comparison.py -q -p no:cacheprovider (11 passed).
  Then ran code/analyze_block15b_frequency.py prepare, followed by run;
  config was persisted before real-data spectra were calculated. Ran
  code/summarize_block15b_diagnostics.py for descriptive supplements.
  A subsequent --plot-only pass shortened a clipped title only.
- Frozen configuration: BP12 only, historical abs(z)**2, plane detrend,
  Tukey alpha 0.1; no phase smoothing. Endpoint local 3x3 MSC >=0.09
  (equivalent to historical magnitude 0.3), wavelengths 40–500 m,
  relative power >0.05 and a canonical half-plane. Raw phase OLS (A),
  direct consecutive circular fit (B), direct lag1/2/4/8 circular fit (C).
  Equal total weight per lag class; real mean TxTime per pair. Search
  +/-3.2144510916 rad/s derives only from the maximum adjacent time gap.
- Reproduced the historical signed slope map to 4.44e-16 rad/s, same peak
  (133,65) and same legacy mask. Corrected coherence accepts 138/214
  preliminary candidates; 15 pass all method-specific validity gates.
  At the fixed peak s_phi A/B/C = +0.4120656492/+0.4322715136/
  +0.4183342902 rad/s. No replacement of the frozen Block4 period.
- Reference sensitivity is numerical roundoff only; telescoping verified.
  Standalone lag4/8 have competing aliases, explicitly retained as invalid
  rather than resolved with external data. Shared-pair confidence intervals
  are not reported. Same-k static contamination is diagnostic only.
- Added a final circular phase-invariance/grid-refinement test. Full suite:
  69 passed, 0 failed, 0 skipped, including SarPy. Formation of dynamic SAR
  phase history remains outside this estimator validation.
- Saved new BLOCK15B configuration, manifests, bin CSV, estimator details,
  summaries, synthetic diagnostics, four inspected figures and report in
  Vandenberg/results/analysis_block15. Small frozen-input SHA guards pass;
  no CPHD/SICD reads, no new looks/downloads, sweep, inversion, commit/push.
- Suggested only a future limited same-k static/slow-contamination study,
  without tuning to the real slope. Stopped after Block15B as requested.

## 2026-09-12 — Block 15C static/slow contamination diagnostic completed

- Reconstructed Block15B attrition from its existing CSV, without changing
  selection: among 138 common candidates, high residuals reject 108/115/122
  for A/B/C; their union is 123, leaving 15. All 74 large-step failures and
  three C branch ambiguities overlap residual failures.
- Added contamination_diagnostic.py, a frozen-design runner, summarizer and
  ten analytic/numerical tests. Called the existing Block15B estimators
  directly with unchanged algorithms, actual BP12 times and validity gates.
- Prepared BLOCK15C_CONFIG.json before computation: slopes .3/.5/.7,
  amplitude ratios 0/.25/.5/1/2, eight relative phases and contaminant
  slope fractions 0/-.2/+.2. Removed B=0 duplicate phases/speeds only.
  Ran 291 noiseless cases, then 50 independent complex-noise replicates
  at each RMS/A=.1 and .3: 29,391 total, approximately 166 seconds.
  SeedSequence uses [150300, case_id, noise_index, replicate].
- Explicit 3x3 proportional/different spectral profiles provide endpoint
  MSC; no single-product coherence. Methods and patch layouts share each
  realization for paired comparisons; temporal pairs are not independent.
- Predeclared event: two valid methods, each >10% biased, agreeing within
  .02 rad/s. Counts 76/291 noiseless, 3773/14550 at noise .1 and 3433/14550
  at noise .3. Noiseless: eight events also have A R2>=.97 and proportional
  MSC>=.8. Mechanism is possible, not identified as the Vandenberg cause.
- Saved complete results CSV, residual NPZ, aggregates, analytic/minimum
  diagnostics, examples, four visually checked figures, report and manifests
  under Vandenberg/results/analysis_block15 with BLOCK15C names. A plot-only
  pass clarified method colors/styles without changing numeric artifacts.
- Commands used .venv-umbra-thesis/Scripts/python.exe -B with bytecode off:
  pytest tests/test_contamination_diagnostic.py -q -p no:cacheprovider;
  code/analyze_block15c_contamination.py prepare, then run;
  code/summarize_block15c_contamination.py; full pytest -q -p no:cacheprovider.
  Ten new tests passed before the grid; full suite 79 passed, zero failed
  or skipped. No new automatic CPHD formation validation is claimed.
- Proposed only a future read-only complex-plane/amplitude/neighbor-bin
  diagnostic on a few fixed BP12 bins. No real temporal-mean subtraction,
  radar array reads, corrections, new looks, downloads, sweep, inversion,
  changes to frozen results, commit or push. Stopped at Block15C.

## 2026-09-12 — Block15D completed: static-offset diagnostic, not correction

- Preserved prior blocks and source radar products. Read the small existing
  BP12 stack read-only; reused Block15B intensity/preprocessing, effective
  times, MSC and fixed 15-bin intersection (already includes the peak).
- Added variable-projection M0/M1 complex-coefficient fits, full signed cost
  profiles, alternative/boundary/flat/rank flags and four contiguous 8-look
  holdouts with all parameters fitted on the remaining 24 samples.
- Froze configuration before synthetic/real computation; six targeted tests
  passed before 44 small synthetic controls, including stationary complex
  AR(1) noise. Then applied the same diagnostic to the fixed real sample.
- Peak (133,65): aggregate predictive NMSE .226091 -> .144975, gain 35.88%,
  all four held-out blocks improve; M0 s=.40607604, M1 s=.40436881 rad/s,
  |c|/|a|=.304740. Conditional parameter stability, not corrected frequency.
- Across 15 dependent bins: four repeated/stable, seven negative gains,
  four positive but insufficiently repeated. Synthetic slow contaminants
  and one no-offset correlated-noise realization also favor M1: physical
  static contribution is not identified by predictive improvement alone.
- No conjugate duplicates. Max coefficient conjugation error 3.48e-16 and
  signed-slope closure 6.45e-11 rad/s. Recorded spatial dependence explicitly.
- Saved config, per-bin/fold CSV, full real/synthetic JSON, summary, nine
  diagnostic figures and BLOCK15D_REPORT.md under analysis_block15.
- Full suite using project-local thesis interpreter with bytecode/cache off:
  85 passed in 18.24 s, no failures or skips. Prior A-C hash guards checked.
- Commands: analyze_block15d_static_offset.py prepare, synthetic, run;
  plot_block15d_static_offset.py; pytest -q -p no:cacheprovider.
- No real offset subtraction, frequency correction, new CPHD processing,
  download, dispersion filter, sweep, inversion, commit or push. Frozen
  T_SAR=17.902230457 s and shortlist unchanged. Stopped at Block15D.

## 2026-09-12 — Block15E completed: correlated-noise and partition robustness

- Froze an OU/proper-complex null design before execution: M0 peak parameters,
  actual BP12 times, tau=0/.5/2/5 s, residual-M0 RMS primary (300 each) and
  residual-M1 RMS sensitivity (100 each), SeedSequence master 150500.
- Refit M0/M1 and their validation subsets for all 1,600 null series. No fit
  failures/exclusions. Frequencies were free; no held-out samples entered fits.
- Added one predeclared real/synthetic split only: eight 4-look test blocks,
  purging two neighboring looks on each available side. It retains 24 samples
  internally and 26 at edges, with about 2.1 s minimum train/test separation.
- Fixed peak remains favorable under this split: predictive gain 50.33%, 7/8
  blocks improve, no stability flags. The original gain remains 35.88%.
- Under primary OU tau=5 s, 60/300 nulls exceed the original real gain; for the
  purged split, 60/300 exceed its 50.33% real gain and 22/300 also improve all
  folds with stable parameters. At tau<=.5 s none reaches the real gain.
- Conclusion: favorable to M1 and robust to the one alternative partition, but
  compatible with a single component plus long-correlated noise. No physical
  static contribution identified and no frequency corrected.
- Saved BLOCK15E config, real/null results, two CSV tables, summary, three
  visually checked figures, report and final manifest in analysis_block15.
- Added four targeted tests for OU covariance/iid behavior, purged support and
  train/test/guard leakage. Full-suite outcome recorded in delivery manifest.
- Multiprocessing pipes were denied by the Windows sandbox; sequential execution
  preserved seeds/design. A NumPy-int JSON conversion changed summary mechanics
  only. Final source hashes therefore appear in the delivery manifest.
- No offset subtraction, radar read, new looks, download, dwell sweep, inversion,
  commit or push. Frozen T_SAR and prior outputs unchanged. Stopped at Block15E.

## 2026-09-12 — Block15F completed: BP12 geometry and transfer-phase sensitivity

- Read only CPHD PVP/metadata through the existing channel reader; explicitly
  did not map or read the CPHD signal block. Reconstructed BP12's 32 disjoint
  pulse supports, exact mean-TxTime representatives and focal surface target.
- Used the original BP12 constant HAE surface (-36.376 m), not SCP or bottom;
  kept the frozen peak (133,65), kx=-.0479965544 rad/m, ky=0 unchanged.
- PVP geometry across look means: view azimuth 85.18--125.09 deg (39.91 deg),
  incidence 22.01--23.89 deg (1.87 deg), R/V 79.82--80.80 s and k dot LOS
  -.04788---.03457 rad/m. Flight bearing changes only .147 deg.
- Audited Block10 physics. Implemented only linear geometric tilt plus the
  first-order density/Jacobian velocity-bunching term using finite-depth
  consistent orbital velocity. Did not invent hydrodynamic/X-band MTF terms
  or double count a separate shift/displacement term.
- Predetermined scenarios (T=13.33 s at h=5/10/20 m; frozen SAR T=17.902 s at
  h=10 m) give transfer slopes +.00532 to +.00623 rad/s, with no near-H=0
  cancellation. This is observable in principle but much smaller than .12
  rad/s; it is conditional and does not identify a physical cause or correct
  any frequency.
- Added four targeted geometric/transfer tests; full project suite 93 passed,
  zero failed/skipped. Nine prior metadata/artifact guards verified. A small
  post-freeze np.ptp compatibility fix changed mechanics only; final hashes
  are preserved in BLOCK15F_DELIVERY_MANIFEST.json.
- Saved report, model assumptions, PVP geometry CSV/JSON, transfer table,
  two reviewed figures, config and manifest under analysis_block15. No new
  radar formation, dwell sweep, download, inversion, commit or push. Stop F.

## 2026-09-12 — Block15G completed: synthetic two-component separability

- Implemented a coefficient-only, fully synthetic Q0/Q1/Q2 experiment with
  the frozen BP12 32-time grid, the exact separable BP12 Tukey-window DFT,
  its window-squared spatial noise covariance, and iid/OU proper-complex
  noise. No CPHD signal block, SAR image, real Q2 fit, download, new look,
  dwell sweep, inversion, commit, or push was performed.
- Frozen calibration has 36 realizations (single constant, single geometry,
  static-offset controls); final evaluation has 60 (five two-component cases,
  12 each). The calibrated primary selection threshold is 0.10. Controls have
  0 selected Q2 fits across 72 transfer/control fits.
- Main result: distinct physical templates at six mode bins recover both
  slopes in 12/12 replicates. A one-bin physical overlap selects Q2 in 9/12
  constant and 12/12 geometry-informed fits but recovers neither slope pair:
  prediction gain is not identifiability. Weak persistent cases recover 8/12
  and 10/12 (constant/geometry); the intentionally unresolved stress case is
  non-identifiable.
- Primary validation is 8x4 purged with two-look guards; Block15D 4x8 is
  recorded only as a secondary descriptive check. Monte Carlo realization,
  never bins or folds, is the counting unit. Geometry-informed H is a known
  synthetic favorable control, not a real-data capability claim.
- Added six focused tests covering window leakage, noiseless recovery,
  covariance/reproducibility, purged guards, Block15D partition, and a
  degenerate template. Full suite: 99 passed, no failures/skips. Outputs,
  reviewed figures, report, protocol, results and delivery manifest are under
  `Vandenberg/results/analysis_block15`. Stop G.

## 2026-09-13 — Block15H completed: BP12 spatial-resolution audit

- Read only the existing BP12 32x288x130 complex stack. Reused the frozen
  Block15B intensity, global-plane detrend, Tukey alpha=0.1 and unpadded FFT;
  peak `[133,65]` was never reselected. No CPHD/SICD signal read, formation,
  dwell sweep, frequency correction, inversion, download, commit or push.
- FFT-bin spacings are 0.00436332/0.00966644 rad/m parallel/perpendicular.
  Explicit Tukey power FWHM is 0.935/0.939 bins, but measured local BP12 lobe
  FWHM is 2.223/1.452 bins. The observed radial scale was therefore used for
  interpretation rather than calling an FFT bin a resolved component.
- Eight local maxima occur in the declared 13x13 support, and the fixed bin is
  largest in only 12/32 looks. A three-bin neighbor is 70.5% of peak power but
  only 1.35 measured radial FWHM away. Classification: amplitude partially
  separated; phase/slope non-identifiable as independent neighboring modes;
  overall not identifiable as multiple spatial components.
- Added eight focused resolution/guard tests. Full project suite: 107 passed,
  no failed/skipped. Eight prior artifact hashes and final delivery hashes are
  verified. Outputs and inspected figures are under analysis_block15. Stop H.

## 2026-09-13 — Block15I compact synthetic discriminant

- Compared a finite-band propagating system with primary-plus-static/OU-slow
  neighbor coefficient families on BP12 time/grid/window conventions only.
  No real coefficients or frozen outputs were classified or modified.
- Held-out evaluation: the predeclared simple persistent-score is conservative:
  0/16 A false calls, 0/32 B detections and 48/48 indeterminate. Seven B
  sequences exceed 10% slope error, none passes frozen validity jointly.
- Full suite remains 107 passed; five prior artifact guards verified. Stop I.

## 2026-09-13 — Block15J completed: multi-lag complex-increment diagnostic

- Performed a read-only audit of frozen Block15I. Its 72-row denominator and
  48-row decision matrix reconcile, but its 107 tests were inherited from H:
  no focused pytest test for the 15I runner exists. All five provenance guards
  still match, while their coverage excludes 15I’s own runner/results.
- Pre-registered one coefficient-only increment-structure score on BP12’s
  irregular times and a fixed Tukey-response support. No real Vandenberg
  coefficient was read. Full sequences, never pairs/bins, are Monte-Carlo
  units; calibration/evaluation seeds are disjoint and geometry is held out.
- Evaluation: 3/16 false A→B, 8/32 B detections, 37/48 abstentions and 4/16
  held-out B detections. The corresponding predeclared utility gate fails;
  no post-hoc classifier or new campaign was added. The frozen 15I rule on
  the same sequences remains 0/32 B, 48/48 abstaining.
- Added ten increment-identity/degeneracy/seed/threshold tests, report,
  config, protocol, CSV, summary, figure and hash manifest under
  `Vandenberg/results/analysis_block15`. Stop J; no real-data application.

## 2026-09-13 — Block15K completed: Vandenberg causal closure

- Froze the protocol and SHA-256 before calculations. Reproduced the frozen
  SICD signed slope exactly and reconstructed the BP12 canonical positive-k
  sign from its stored conjugate pair without selecting a new peak.
- Used only existing products: three enlarged SICD intensity looks and the
  32-look BP12 stack. No new raw CPHD/SICD read or formation was required.
- On the common 1440x650 m ground grid and three projected temporal kernels,
  slopes are -0.403462 and -0.403685 rad/s; residual 0.000223 rad/s. Kernel
  cosine is 0.985–0.992 and k mismatch is 0.0116 delta_eff.
- The historical 0.061093 rad/s gap closes numerically by 99.64%, but the
  dominant spatial/temporal changes interact and vendor SVA/PFA weights are
  unavailable. This is partial pairing, not a causal decomposition or a new
  corrected frequency.
- Applicability: Level 1 kinematic detection supported with limitations;
  Level 2 wave-frequency identification not identifiable; Level 3 bathymetry
  not supported with mandatory abstention. Vandenberg is frozen as a
  development stress test, not a physical validation scene. Stop K.
- Added 18 focused path-matching/gate/provenance tests; full suite 135 passed,
  zero failed/skipped. The Block15K manifest hashes essential 15I–K artifacts.

## 2026-09-14 — Block17 selector consolidation

- Selected Block17 as the first unused block identifier and froze protocol/config
  before calculations. Work remained offline: zero network requests and zero SAR
  reads; Blocks 15–16 and Vandenberg results were not modified.
- Reproduced the archived Block16A baseline exactly (A=0, B=1, C=33,
  D=10106, E=0). No category changed. Four measured-reference rows cannot be
  re-audited for joint per-band completeness because the archived CSV omits the
  per-bin arrays; this is recorded as abstention, not absence.
- Added corrected primitives for admissible-reference selection, joint
  directional masks, missing-safe integration, separate CPHD/SICD budgets and
  honest ROI/count semantics. Confirmed the historical 80% marine gate existed.
- On 32 archived irregular BP12 times, the corrected Gaussian-energy generator
  realizes its requested width (ratio 0.996–1.000); the legacy generator realizes
  about 0.706–0.708, confirming sigma/sqrt(2) narrowing.
- Added dispersion derivatives, k–omega covariance propagation, finite-band and
  off-grid tests. These are exploratory, not ranking gates. Full suite: 179
  passed, zero failed/skipped. Stop at CHECKPOINT_17; no commit or push.

## 2026-09-14 — Block18 bounded per-bin reference recovery

- Derived exactly four targets from the Block16A measured-spectrum table and
  froze Block18 protocol/config before network access. No manual outcome-based
  scene selection was used.
- Queried only NDBC station 42084 aggregate metadata/time and four server-side
  spectral subsets: 7 HTTP transactions, no retries, 560,916 response bytes;
  maximum response 499,416 bytes. No annual/CDIP fallback was needed.
- Current aggregate indices and timestamps match the historical observations.
  All four remote subset hashes match Block16A exactly. A manifest audit then
  located the same four original payloads already under Block8; the initially
  missed local discovery and subsequent exact remote identity check are both
  retained in provenance.
- All four references pass 50 km/3600 s limits and have 100% density and joint
  directional-energy coverage in the frozen 0.04–0.25 Hz band. Directional
  moments remain non-unique and 34 km proximity does not prove local physical
  representativeness.
- Hm0, peak period/frequency/direction and peak moments reproduce Block16A.
  Only the 2026-03-14 `f<=0.1 Hz` fraction changes, from 0.00140647 (trapezoid)
  to 0.00187529 (band sum); it remains far below the 0.5 gate.
- Categories remain D/D/D/C because unfavorable geometry, weak sea state and/or
  nondominant measured swell remain. No other acquisition was reclassified.
- Offline reparsing reproduces all 392 normalized bin rows and metrics exactly.
  Full thesis-environment suite: 187 passed, zero failed/skipped. No SAR access,
  Vandenberg reopening, formation, sweep, inversion, commit or push. Stop at
  CHECKPOINT_18.
