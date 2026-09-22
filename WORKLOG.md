# Work log

## 2026-09-18 — Complete in-repository layout migration

- Continued the pre-existing staged directory moves after explicit user confirmation. Root and Git remote remain unchanged; shared code/tests/environments stay at root. Umbra artifacts live under umbra/, Duck/CSK/TSX/FRF under duck_frf/, guides/checkpoints under docs/, maintenance under scripts/.
- Migrated executable path literals and dynamic historical-path readers. Added repository_paths.json and explicit resolver; frozen manifests retain original paths/content and expose original versus resolved paths during audits.
- Restored native-layout ignore and byte-preservation rules. No radar data edits, environment relocation, download or scientific reprocessing. See docs/REPOSITORY_LAYOUT.md and docs/reorganization/ for tests/hash audits and remaining historical-reference limitations.

## 2026-09-18 — Block34 operational Duck/FRF client

- Delivered stable mission-neutral CLI, separate inputs/config/budgets, persistent named tranches, verified cache reuse, early validation and explicit partial dossiers. See FRF_QUICKSTART.md and CHECKPOINT_34.md.
- Three original October events recovered: waves/spectra/QC, currents/wind/level, three bounded survey subsets NAVD88. New tranche: 25 HTTP / 3,253,569 bytes; historical consumption not determinable. Survey 20211013 metadata timeout remains explicit.
- 8m-array longitude variable/nominal conflict preserved without sign correction; position unresolved, wave values unchanged. WR/AWAC native peaks still differ; no automatic physical explanation or scene selection.
- 320 full tests; 78 isolated already included; five offline CLI smokes, mock budget/resume tests, 15 equivalent cached-output comparisons, visual QA. Local isolated source copy, not a GitHub clone; existing thesis interpreter, not clean installation.
- Frozen artifacts/checkpoints audited, current provenance/relative manifest and exact pending file list saved. No radar access, inversion, dwell sweep, commit/push, or changes to frozen outputs/cache/budgets.

## 2026-09-18 — Block33 offline FRF correction

- Reproduced 11 reported failures before source edits; froze 438 available Block32 artifacts/cache files. No real HTTP, source cache/budget reset, SAR or changes to frozen dossiers/configs/manifests.
- Corrected metadata-only new-product inventory, calendar/year/leap context months, separate far-event windows, cross-file provenance/duplicates/grids, missing/zero spectra, selected-sample positions and both deployment boundaries, Content-Length truncation/resume. Defaults no longer overwrite frozen Block32 output/cache.
- 310 full ordinary tests passed; 68 isolated corrected-source client/Block30 tests passed, without private cache/radar/credentials. Explicitly audited pending lightweight source/test/fixture files and matching pinned installed dependencies; no clean-install or published-HEAD claim.
- Four cached regenerated dossiers retain 604 compared observation rows, exact timestamps/offsets/QC and spectral/context-distance values; 438 baseline file hashes and 163 historical input hashes verified unchanged. Historical corrected-code hash mismatches are separate, not concealed as artifact verification. Manifest paths relative to root and absolute historical remapping explicit.
- Saved protocol, defects, tests, clone input/dependency audit, regression comparison/dossiers, frozen audit and manifest under Block33_frf_offline_correction. Stop CHECKPOINT_33 with source-layout/coverage/deployment/history limits; no commit/push.

## 2026-09-17 — Block32 mission-neutral FRF observation client

- Read task/repository instructions, frozen Block30 code/cache/tests/notes and original Block31 EOWEB record 11. Created next unused block32, strict adapters and reusable library/CLI, preserving all frozen inputs/results.
- Reused scalar Block30 parser; extended inline scalars/ND GRID data and validated shapes/maps. Added per-variable masks/QC associations, historical-position conflict/deployment checks, WGS84 polygon/ROI distances, spectra/profile JSON tensors, plots and manifests. Public anonymous endpoint discovery, verified TLS, no radar/browser/login bypass.
- Created persistent 40 HTTP/100 MiB tranche before first request. Verified official root/family/instrument/year/service metadata and event subsets. Reused 86 unique logged legacy payloads after SHA256/newline verification. Final consumption 40 transactions/2,412,291 bytes, including one partial failed AWAC June spectral stream (1,048,576 bytes); previous historical cumulative consumption non determinabile, not zero.
- Corrected supplier NaN / NumPy boolean JSON serialization offline. Fixed early bare-DAP URL logging '=' canonicalization via original cache-key SHA proof. No payload or Block30 rewrite. Final dossiers/inventory/time-only CLI reprocessing cached/offline, no new HTTP; new partial-error logging retains bytes explicitly.
- October Waverider/AWAC 62×72 spectra + moments/QC, published Hs/Tp/peak-band direction, EOP winds, AWAC profiles and preliminary NOAA levels recovered. June contemporary AWAC bulk retained independently of stale Waverider, plus current profiles. Missing June wave QC/spectra/wind/level and detailed survey date/datum/method/coverage explicitly incomplete at budget exhaustion; survey download opt-in, no bounding-box coverage inference/GEBCO.
- TDX timestamp exactly 2021-10-13T23:00:15.669Z, catalogue not aperture center. Waverider outside TDX footprint ~690 m from edge/~3707 m centroid; source nominal coordinate conflicts 24/46 m propagated. No automatic direction/height/depth/interpolation correction or mixing a tile state.
- Final full suite 269 passed in 23.00 s (24 new offline tests). Frozen audit163 files zero mismatches; Block4 SAR-only golden SHA unchanged. REPORT/TEST_REPORT/CHECKPOINT32 and manifests record scopes, limits and hashes. Stop client verification; no SAR processing/inversion/selection/commit/push.

## 2026-09-16 — Block30 FRF conditions execution

- Executed smoke, October 2021 waverider-17m subset and full no-argument run with the thesis interpreter. Initial proxy refusal diagnosed; public FRF transport used only with approved escalation.
- ASCII parser/monthly naming verified; batched available scalar variables, cached payloads/provenance and corrected missing-value/error handling. Verified awac-8m catalog covers only 2007–2014, not target years.
- Full run produced 72 conditions and 18 gate rows, 79 requests / ~3.5 MB; final repeat entirely cached, zero new requests. Scene CSV SHA256 unchanged, no radar touched.
- Measured true-north MET from-direction used for propagation and axial range mismatch, no assumed 250 degrees or directional corrections. October scene: Hs 1.108 m, Tp 9.547 s, mean from 59.255 degrees, phi 40.2 degrees, +15 min.
- No nearest-any-instrument sample exceeds 60 min; selected waverider-17m is stale for 1941935 (-29066.8 min) and 1942455 (-29784.8 min). These rows explicitly diagnostic only / temporally unusable; nearest AWAC offsets +3.2/+5.2 min, no automatic substitution.
- Final complete suite: 245 passed in 20.61 s. Corrections/limits in Block30_duck_csk_preflight/FRF_EXECUTION_NOTES.md. No commit/push, no frozen-block modification.

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

## 2026-09-15 — Block21 frequency-validation selector

- Froze a new protocol/config and started from the complete 10,140-row archived
  catalog snapshot. Block19 was not used as an input and Block20 was not audited.
- Recomputed deterministic local-metric water ROI geometry for all footprints,
  including short scenes. Found 2,591 scenes with a fully-water square of at
  least 250 m; coast and footprint-edge clearances are distinct fields.
- Removed dwell/cycle, 80% marine, ≥10 s period, long-energy and bathymetry gates.
  SICD or CPHD is accepted as a complex path; GEC/preview alone is not.
- Reused four Block18 references offline, froze a diversified 12-row remote
  queue, and recovered five additional admissible NDBC per-bin references.
  Remote use: 28 transactions, 2,377,820 bytes; seven queue entries failed and
  remain explicitly distinct from unqueried catalog rows.
- Derived period and direction from the same contiguous half-power dominant
  band. Produced a five-scene frequency-validation shortlist, cards and maps.
- Best current candidate is the 2025-11-15 Umbra-09 collect near NDBC 46268,
  recommended only for bounded SICD metadata preflight, not yet SAR download.
- Stop at CHECKPOINT_21; no SAR object accessed.

## 2026-09-15 — Block22 geographic, visual and SICD metadata preflight

- Preserved Block21 and Vandenberg frozen outputs and did not inspect Block20.
- Corrected the Block21 coast-distance method: original Natural Earth polygon
  boundaries are used, never boundaries introduced by clipping land to the SAR
  footprint. Reported center and polygon clearances separately from product-edge
  distances, plus buoy-to-center and buoy-to-polygon distances.
- Verified all five finalist ROI polygons as fully contained in mask-relative
  water. Candidate 1 contains station 46268 and has >1 km coast and edge ROI
  clearance at the coarse mask resolution.
- Recovered candidate-1 SICD XML from an exact 2 MiB NITF tail byte range after
  the standalone XML returned 404. No image pixels were read. Processed aperture
  is 6.587138417 s, distinct from 7.495363670 s IPP support and 7.6 s catalog.
- Verified local range axis 136.8276° modulo 180. Its 67.17° axial mismatch from
  buoy propagation 24.0° makes candidate 1 unsuitable for the intended
  range-aligned validation despite excellent reference proximity.
- No small official preview was advertised; wave structure remains not
  evaluable. Existing Vandenberg GEC/ROI geography was audited read-only and the
  Block15K development-stress-test classification remains frozen.
- Stop at CHECKPOINT_22. Candidate 1 is not recommended for full download.

## 2026-09-15 — Block23 candidate-2 metadata preflight

- Audited only frozen Block21 finalist 2. Public STAC and vendor metadata verify
  UUID, Umbra-10, spotlight, right-looking, VV and a 15.101624 s collect span.
- Corrected a critical availability interpretation: STAC declares private SICD
  and CPHD assets, but neither exists in the frozen public S3 listing. Both
  declared filenames and normalized public aliases return HTTP 404.
- Therefore SICD processed aperture, Timeline/IPP, local Grid Row range axis,
  valid-data support, CPHD channels/PVP and TxTime span remain unverified. No
  pixel or signal array was read.
- Reused the frozen NDBC 46268 band without network access. Vendor center
  azimuth gives only a provisional ~71.82° axial mismatch; it is not substituted
  for the unavailable SICD local range geometry.
- Preserved the Block22 ROI audit: ~181.6 m mask-coast clearance and only ~90.1 m
  STAC-footprint clearance. No unsupported ROI optimization was attempted.
- Classified candidate 2 as non-priority under the present public access path.
  Stop at CHECKPOINT_23 without download, Block20, other candidates or commit.

## 2026-09-16 — Block27 representativity continuation, offline checkpoint

- Preserved the pre-existing Block27 queue/report and added versioned outputs
  under `Block27_frequency_query/representativity_v1` (23 scenes, four zones).
- Reused verbatim Block21 ROI polygons; all 23 are contained in their catalog
  footprints. This is not verification of SICD valid-data/pixel support.
- Revalidated the four Block18 42084 raw hashes and reparsed all arrays with
  individual masks, joint masks and reconstructed bin widths offline. Queue
  target 42094, actual reference 42084 and nearest-any-instrument GRBL1 are
  distinct; instrument capability cannot be inferred from proximity.
- Inventoried Block18 (392 bins/four scenes) and Block21 (388 bins/five newly
  recovered scenes) separately. Produced four preliminary coastline maps and
  exposure diagnostics without Snell correction or unsupported site labels.
- Three focused offline regression tests passed. No new remote requests or
  downloaded bytes. Remote recovery is explicitly guarded pending reconciliation
  of the already-started phase's cumulative request/byte budget: no ledger or
  payload/state for that phase was found in Blocks25–27. Partial status and
  missing geographic/operator/event-model evidence are recorded, not called
  completed validation. No SAR/AIS/Vandenberg/sweep/inversion/commit/push.

## 2026-09-16 — Block27 independent authorized recovery tranche

- User explicitly replaced the unknown previous remainder with a new 30 HTTP /
  20 MiB tranche. Historical spending is `consumo storico non determinabile`,
  numeric historical counters null; no old cumulative-limit compliance claim.
- Preserved v1 and resumed its reconciled table in `representativity_v2`;
  initialized the ledger before network and persisted live budget counters.
- Included 13 sandbox proxy-refused attempts in the new tranche; authorized
  direct transport then recovered station 51209 DDS/DAS/time and the event's
  full 64-bin density/directional spectrum (Tp 13.3333 s, +502.2 s offset).
- Reused all four verified 42084 references locally. NDBC spectral endpoints
  for 42087/41052/42094 returned 404; alternative spectral availability remains
  unresolved, not globally absent. Local CDIP 246 products cover 2019 only,
  outside queued 2025–2026 acquisitions; do not transfer DWR-M3 deployment.
- Retrieved station pages 42087/41052 and marine model documentation. Operator
  and adequate Tobago coastline attempts failed; no new event-model subset.
- Stop at the actual new tranche limit: 30 transactions, 1,183,903 bytes;
  five spectra hash-verified/reparsed offline identically, 18 scenes without an
  established event per-bin reference. Versioned report/maps/state/manifest
  record geographic, sensor and model limits. No SAR or automatic expansion.

## 2026-09-16 — Block28 circumscribed Samoa complex-metadata preflight

- Reused representativity_v2 Samoa spectrum/masks, station, ROI and temporal
  association offline. No new wave reference or expanded scene search.
- Initialized a separate persistent 20 HTTP / 20 MiB / 5 MiB-response budget.
  Initial pertinent HEAD failed at sandbox proxy localhost:9; diagnosed before
  other endpoints and used only approved external network execution thereafter.
- Verified public SICD 2,551,099,862 bytes and extracted only NITF main-header /
  DES XML spans, never image-segment bytes. UUID, collector, polarization HH
  and processing metadata agree with official STAC.
- Complete cached prefix listing revealed public CPHD 25,234,138,880 bytes
  omitted from the normalized STAC inventory. Read only its header/XML and
  three 8-byte PVP TxTimes. Source catalog and frozen results stay unchanged.
- SICD processed aperture 2.975363044 s is separate from catalog 3.6 s,
  Timeline 3.700802707 s and CPHD first-last TxTime 3.691770699 s.
- ROI fully contained in sampled SICD ValidData with ~494 m geographic margin;
  surface assumptions and HAE sensitivity documented. Distinguished horizontal
  Grid Row, local LOS and surface coordinate push-forward in squinted PFA:
  frozen buoy-band mismatch ~39.10° to LOS versus ~77.86° to surface Row.
- Saved three nominal look plans with approximate resolution, no cycle/dwell/
  phase gate and no independence claim. No small advertised official preview;
  wave structure remains unevaluable.
- 26 focused tests passed. Actual budget 16 transactions/59,642 bytes, including
  proxy failure and one repeated vendor JSON 404 at technical resume; all
  attempts retained and failure caching corrected. Stop CHECKPOINT_28, decision
  B: Doppler–PVP/PFA timing and oblique-support leakage need verification before
  phase interpretation. No automatic download/formation/real frequency, no
  AIS/Block20/inversion/Vandenberg, no commit/push.

## 2026-09-16 — Block29 Samoa PFA Doppler–time gate

- Created the first unused block identifier/directory, captured commit and
  pre-existing dirty worktree, froze config/protocol before new PVP retrieval.
- Reused Block28 SICD/PFA/CPHD XML and ROI/reference provenance. Recovered only
  the complete compact PVP block: 8,165,216 bytes, 21,716×376-byte records.
  Phase A uses 3 transactions including one proxy-refused HEAD; no signal.
- Added reusable structured-PVP/PFA projection/kernel/Jacobian routines.
  Parsed big-endian float and integer fields using official CPHD dtype. Full
  time continuity and SIGNAL validity pass; phase-plane PVP/metadata angle
  and independent ARP comparisons are excellent (~1e-8/~3.5e-7 s equivalent).
- Explicitly inverted angle atan2(k_col,k_row), with Row-frequency coupling,
  scene-interaction time and geometric output-k versus time-weight cases.
  Increasing Col bands have reverse chronology, verified numerically.
- Frozen Gate A is CONDITIONAL: combined local-gradient center sensitivity
  0.392281 s exceeds 0.05 s; 19/90 local kernels not identifiable under the
  assumed support. Local/global PFA transport is unresolved; shifts may be
  deterministic focus-phase/carrier effects, not an ocean/SAR timing bias.
- SICD download remains NOT STARTED. No alternate formation or actual phase
  retrieval. Small actual-mask-geometry synthetics are explicitly image-domain
  diagnostics, not physical SAR simulation or real-data leakage validation.
- Complete thesis-interpreter suite: 242 passed, zero failed/skipped. Saved
  versioned report/gate/kernels/figures/phase-A-and-B states/test report/manifest;
  stop CHECKPOINT_29. No q/inversion/dwell sweep/CPHD signal/Vandenberg/AIS,
  no commit/push, no frozen artifact/hash rewrite.

## 2026-09-18 — Block35 Duck Sentinel-1 spatial selection

- Audited retired Block33 S1 scripts: point-only query, incomplete pagination,
  volatile budgets, duplicate FRF parser, fixed incidence/depth/gradient and
  unvalidated cutoffs. Replaced with deprecated wrappers of stable entry points;
  native next free result directory is duck_frf/Block35_s1_spatial_selection.
- Frozen protocol/config before public requests. Actual documented CDSE OData
  October query completed: eight IW SLC products, five physical datatake passes;
  all UUIDs retained, five covering slices, no date extension/fallback needed.
- Reused verified FRF payloads with operational client. Pass A monthly scalar/QC
  for every product; Pass B spectra/ancillary for five passes. Smaller distinct
  projection recovered WR17 E(f)/moments after 3D timeout; failed URLs not retried.
- Traversed complete bounded geographic survey vectors before filtering. Oct24
  provides actual northern-ROI support; nominal nearest Oct27 has zero points
  there. Kept per-point dates, NAVD88/geoid2003, NAD83-to-WGS84 geolocation caveat,
  sample gaps/coverage, measured segment scales and nonlocal frequency limits.
- Selected October28 S1A IW SLC UUID c49a9c1f-9b00-5676-ab05-683975d898a2 as a
  conditional first technical spatial trial; October11 is alternate. Public
  Assets/Nodes and two quicklooks verified; annotation XML returned 401 with no
  configured credentials. Local range/incidence/burst valid support remain open.
- New tranche 73 charged attempts (72 HTTP + one conservative persistence
  reserve), 7,041,606 bytes. Includes failures/400 expansion correction/401;
  historical consumption not determinable from this ledger, no old-budget claim.
- Analytic dispersion derivatives verified with toy finite differences only;
  no actual inversion, universal FFT uncertainty/RMSE bound or imposed SAR k.
- All 810 frozen hashes unchanged. Full suite/test provenance in Block35 report.
  No SAR pixels/download/formation/dwell sweep, no Vandenberg, no commit/push.

## 2026-09-19 — Block36 Duck Sentinel-1 annotation preflight

- Kept the Block35 October 28 product/ROI fixed and made no October 11 query.
- Added a secret-safe CDSE bearer loader, persistent metadata-only 40-request /
  50 MiB tranche, strict manifest/annotation allow-list and resumable full-product
  downloader that remains unexecuted.
- No credential was configured, so no protected request was attempted: actual
  usage 0 transactions/0 bytes. Subswath, burst, valid coverage, local range,
  incidence and Jacobian remain explicitly unknown; gate `BLOCKED`.
- Added secure Sentinel-1 IW XML parsing, exact per-line valid-burst support,
  geolocation/Jacobian and k-transform routines plus a preregistered spatial
  intensity-spectrum plan. No pixel read, frequency retrieval or inversion.
- Initial blocked-state focused suite reached 16 passed; final authenticated
  artifact counts are recorded below. Frozen audit remained unchanged.

### 2026-09-20 — Block36 local CDSE login preparation

- Replaced the manual-token-only setup with a root Git-ignored `.env` holding
  `CDSE_USERNAME`/`CDSE_PASSWORD`; added an empty tracked `.env.example` and
  verified `.env` is absent from the Git index. Existing files are never copied
  or overwritten automatically. Direct `CDSE_ACCESS_TOKEN` remains supported.
- Implemented the official CDSE Keycloak password flow (`cdse-public`), one
  hidden local TOTP prompt when required, in-memory access/refresh tokens,
  expiry handling, maximum three auth requests and one post-401 metadata retry.
  Authentication uses the existing Block36 budget; secret requests/responses
  are never cached or logged. No live login or protected request was made.

### 2026-09-20 — Block36 authenticated completion

- Login succeeded without MFA. Corrected the real SAFE lexical UTC form: its
  timestamp fields omit `Z` but are UTC by field semantics; added regression.
- Retrieved/hash-verified only manifest, VV IW1/IW2/IW3 annotations and the
  matching IW3 calibration/noise XML. No TIFF, SAFE/ZIP or SAR pixel read.
- Fixed ROI is 100% valid in IW3 burst 0, with no seam. Range bearing
  80.571242°, azimuth 350.453641°, incidence 44.163763° and explicit local
  Jacobian; measured FRF axial mismatch is 14.23°/14.16°.
- Gate `READY` for the first spatial trial only. Final ledger 12/40 requests,
  3,819,945/52,428,800 bytes, including one retained sandbox transport failure.
  Focused tests 17 passed; authoritative suite 360 passed; frozen audit 810/810.
  Full product download remains not executed. No commit/push.

## 2026-09-20 — Block37 Duck Sentinel-1 real spatial trial

- Froze product, VV/IW3/burst-0 support, three FRF windows, radiometry,
  taper/detrending, FFT convention and stability gates before reading pixels.
- Downloaded only the frozen UUID: 7,799,368,890 bytes, vendor MD5 matched and
  local SHA-256 recorded. ZIP and extracted SAFE remain Git-ignored.
- Bounded complex reads are entirely valid. Primary bilinear spectra are stable:
  wavelength 76.63–77.14 m, axial bearing 85.36–85.88 degrees and
  lobe/background 54.8–93.6.
- Detrend/taper/raw variants retain that family. Nearest resampling selects
  42–45 m at 43–44 degrees; noise subtraction masks 12–13% and is left
  unavailable without filling.
- Complete WR17/AWAC spectra support a broad compatible system. Conditional U=0
  depths are 4.535/5.477 m, with frequency/current sensitivity about
  3.72–6.57 m. NAVD88 bed elevations are not event depth, so validation remains
  unestablished.
- Focused suite 10 passed; full suite 370 passed; frozen baseline 810/810.
  No commit or push.

## 2026-09-21 — Block38 scene-generic S1 transect tool (paper-inspired) and geolocation fix

- Implemented Mudiyanselage et al. (2024) window overlap (50 m steps along transects)
  and contour-blob peak identification (`code/s1_paper_peak.py`). The released
  Mendeley code contains only the ArcPy subset extractor, `FastPeakFind.m`, `cmocean.m`;
  the contour main script is absent. Paper-text reading is primary; the FastPeakFind
  recipe loses the 1–3-pixel top-level blobs on synthetic speckled swell (0/20 found).
- Replaced the Duck-specific runner/JSON configs with one scene-generic CLI
  `code/s1_transect_bathy.py` (bbox + SAFE; SAR-derived instantaneous land/sea mask,
  coastline, seaward transects; native-sample spectra; optional in-situ period).
- **Found and fixed a geolocation error in Blocks 36/37** (line-number vs burst-time
  interpolation, ~105 lines ≈ 1.4 km along azimuth, 12 % Jacobian line-spacing error):
  `docs/NOTE_S1_GEOLOCATION_BURST_TIME.md`, `code/s1_iw_geometry.py`. Block37
  λ≈77 m result and its survey context are superseded; frozen files untouched.
- Duck run (`duck_frf/Block38_s1_transects_duck`, N=4 alongshore averaging): 25
  transects, 1279 windows at sea, 1011 identifiable. Band-averaged spectra: λ
  92→110→128→129→127→142→147 m from 0–500 to 3000–3500 m offshore; argmax and
  contour agree within a few %. Paper-literal N=0 is speckle-dominated.
- `duck_frf_compare.py` (18 overlapping windows with Oct-24 survey, xFRF 500–865):
  WR17 T=11.765 s, U=0 → median implied event water level +0.41 m NAVD88,
  RMSE vs −z 1.72 m, r=0.57; AWAC T=10.81 s → implied η +2.3 m (implausible).
  Not a validation: η unverified, small correlated sample, period band gives
  h ≈ 5.5–10.5 m.
- Tests: 20 new pass (Linux VM env); full suite in VM 370 passed, 20 failed, all
  failures in files not touched here (FRF/credential/Block7 env-dependent). Run the
  authoritative suite in `.venv-umbra-thesis`. No commit/push.

### 2026-09-21 — Block38b GRD baseline (paper reproduction at Duck)

- Downloaded only the needed SAFE members of the same-datatake GRDH
  (`S1A_IW_GRDH_1SDV_20211028T230637_..._04C765_8C9F`, UUID 45382fde-…): manifest,
  VV annotation/calibration/noise and VV measurement (864,714,122 B), each MD5-verified
  against manifest.safe (`code/download_s1_safe_members.py`; the whole-product endpoint
  returns 501 on Range, the Nodes endpoint supports it). Stored in Git-ignored `data_s1/`.
- `s1_transect_bathy.py` now reads GRD too (`GrdGeometry`, zero-filled borders invalid).
- Geolocation: GRD vs SLC σ0 maps cross-correlate at 0.94 with GRD displaced ~75 m E,
  ~37 m S (≈ range direction); GRD vs survey z≈0 edge −5.8 px (58 m) in range. SLC
  matched the same survey test within 0.8 samples. Both grids use h≈0 m ellipsoidal
  at Duck while the sea surface is ~−37 m (geoid): absolute range geolocation remains
  uncertain at the ~40 m level; not corrected.
- Comparison table: `duck_frf/Block38_s1_transects_duck/config_comparison.txt`.
  Band-ensemble λ SLC vs GRD agree within 1–4 % to 2 km (92/93, 110/111, 128/130,
  130/135 m): independent check of the native-SLC spectral chain. Paper-literal GRD
  1280 m windows: stable (p90 jump 13 %) but no cross-shore trend (ρ≈0) and no window
  inside the survey footprint. GRD 512 m N=0 far less speckle-dominated than SLC N=0
  (λ p10 ≈ 80 m vs ≈ 30 m). Survey comparisons (18–23 correlated windows, depths
  6–8 m) cannot discriminate methods.

### 2026-09-21 — Ground-truth retrieval unified (`frf_ground_truth.py`)

- New linked modules: `frf_client/dem.py` (FRF surveyDEM nearest in time via the
  budgeted Transport/THREDDS walker), `coastal_dem.py` (NOAA NCEI CUDEM 1/9″ tiles
  chosen from the official url list, bbox window by HTTP range), CLI
  `frf_ground_truth.py` (FRF client observations + DEMs + merge + GROUND_TRUTH.json).
  Tests `tests/test_ground_truth.py` (3 pass). README `code/README_FRF_GROUND_TRUTH.md`.
- Duck 2021-10-28 23:06:39Z (tranche `gt_s1a_20211028_b`, first attempt
  `gt_s1a_20211028` exhausted its 50-request template budget before water level):
  water level +0.235 m NAVD88 at 23:06 (predicted −0.346, residual/surge +0.581;
  NOAA preliminary); AWAC 11 m current E +0.01, N −0.30 m/s (23:45, +38 min);
  wind 9.0 m/s from 56°; spectra WR17 Tp,disc 11.76 s, AWAC 10.81 s, 8 m array
  12.90 s, WR26 10.81 s (Hm0 1.56–1.78 m).
- Bathymetry: FRF surveyDEM 2021-10-21 (−8 d, x 50–950, down to −9.2 m) + CUDEM
  (NC tiles n36x25 w075x75/w076x00 2019v2, down to −20.5 m in bbox). Overlap
  FRF−CUDEM underwater: median +0.09 m, p10/p90 ±0.84 m.

### 2026-09-21 — BlueTopo in ground truth; forward λ check on certified bathymetry

- `coastal_dem.read_bluetopo`: NOAA OCS BlueTopo (4 m, NAVD88) with per-cell vertical
  uncertainty and contributor table (survey id, institution, dates). Duck bbox: 4–12 m
  from USACE/JALBTCX topobathy lidar Jun 2019 (unc ≈0.8–0.9 m); >12 m mostly NOS
  H00965 (1868) interpolated (unc ≈2.6–2.8 m). FRF 2021 − BlueTopo at 8–10 m −0.11 m
  (CUDEM −0.75 m); AWAC bed ≈ −11.6 vs BlueTopo −11.49 (CUDEM −10.28).
- `frf_ground_truth.py` priority FRF survey > BlueTopo > CUDEM; 7-band GeoTIFF (bed,
  source, event depth, uncertainty, contributor, source year, interpolated flag);
  `wave_spectra.json` with full gauge E(f).
- `s1_transect_bathy.py --save-spectra` (window spectra + footprint corners).
- `forward_lambda_check.py`: certified windows only (footprint uncertainty ≤ 1 m, not
  interpolated, source ≥ 2016, depth ≤ 12 m) → 128 SLC / 157 GRD windows, depths
  7.4–10.7 m (512 m windows near shore touch uncertain cells). Gauge E(f) mapped to
  E(k) at footprint depths (U=0). SAR paper-peak λ vs predicted E(k) centroid:
  SLC +7.6 % median (p10/p90 −8/+20 %) with 8 m array; +10.6 % with WR17; +12.3 % with
  AWAC. GRD +5.0 % (−8/+15 %). SAR λ follows λ(h) at the 8 m-array peak (12.9 s).
  k²-weighted prediction dominated by spectral tail (no cut-off/noise model): not used.
- H12859 (NOAA multibeam 2016) proposed by user: BAG extent lon ≥ −75.648, lat ≥ 36.19,
  i.e. ≥ ~9 km offshore of Duck; no overlap with current windows (≤ 3 km offshore).

### 2026-09-22 — Offshore gap 3–9 km: legacy grids ranked by measured accuracy

- Sources found for the gap: USGS OFR 2011-1015 `nhatt` (SwathPlus 2001–02 + singlebeam
  1999, 40 m, MSL) covers 94 % of the 3–9 km band; USGS/VIMS LARC swath 2002 (MLW,
  nearshore only); lidar USACE 2016 Duck reaches 23 m / 6.5 km (7 % of band); NOAA
  W00331 lidar 2014 only to −5.6 m; H12859 MBES from ~10 km. NOAA NCEI hydro index has
  nothing modern in between.
- Datums from NOAA CO-OPS 8651370 (epoch 1983–2001): MSL −0.128, MLW −0.623,
  MLLW −0.667 m NAVD88.
- `frf_ground_truth.merged_bathymetry` rewritten: sources ranked by measured accuracy
  (FRF survey > BlueTopo modern > legacy grids bias-corrected against modern data deeper
  than 9 m > BlueTopo interpolated > CUDEM); new band 8 = empirical uncertainty (NMAD vs
  higher-ranked data). `--legacy-grid PATH|URL.zip,OFFSET,LABEL,YEAR`
  (`coastal_dem.legacy_spec`).
- Duck extended bbox (−75.79 36.15 −75.62 36.22), `outputs/ground_truth_s1a_20211028_ext`:
  nhatt bias vs modern +0.70 m (by depth 9–12 +0.87, 12–15 +0.68, 15–18 +0.66, 18–22
  +0.57, 22–30 +1.05), residual NMAD 0.26 m → corrected −0.70 m. VIMS 2002 bias −0.05,
  NMAD 0.32. Empirical accuracy: lidar USACE 2019 vs FRF 2021 +0.20 / NMAD 0.15; NOAA NGS
  2019-20 lidar vs FRF +0.42 / NMAD 0.72 (nearshore, excluded at 0.5 m); lidar 2016 Duck vs
  corrected nhatt NMAD 0.17 (upper bound). 3–9 km band: 85–99 % corrected nhatt,
  median empirical uncertainty 0.26 m, ≥ 98 % of cells ≤ 0.5 m.
- `forward_lambda_check.py` now certifies on EMPIRICAL uncertainty ≤ 0.5 m (default),
  not interpolated, no age criterion by default; max depth 30 m. Existing SLC N=4 run
  (≤ 3 km offshore) on the extended ground truth: 1116 certified windows, depth 7.3–17.5 m;
  SAR paper λ vs predicted (8 m array E(k) centroid) median −2.9 % (p10/p90 −37/+10 %);
  by depth bin within ±8 % except 15–16 m (−15 %).
- SAR rerun out to ~10 km pending: the Windows folder did not mount in the device shell.
  Code was edited via staging and committed back; test `test_ground_truth.py` 4 pass.

### 2026-09-22 — Whole-scene forward check to ~27 m depth

- `s1_transect_bathy.py --chunk I N / --finalize N` (partial runs for the 180 s device
  shell; alongshore averaging done after merging). `forward_lambda_check.py`: npz power
  decompressed once, dispersion vectorised over depths, prediction on a fine k grid
  (the SAR bin width 2π/L had quantised the prediction by ~10 %), windowed footprint
  rasterisation. New `forward_lambda_combine.py` (per-window prediction from the gauge
  nearest in depth).
- Ground truth `outputs/ground_truth_s1a_20211028_ext20` (bbox −75.79 36.15 −75.56 36.26):
  nhatt bias +0.70 m, residual NMAD 0.30 m; by depth 9–12 +0.79, 12–15 +0.73,
  15–18 +0.66, 18–22 +0.57, 22–30 +1.05 (single constant ⇒ ~0.35 m error at 22–30 m).
- SAR runs (SLC IW3 VV, N=4): `ext_near` 512 m windows 0.25–6 km, 53 transects, 5200
  windows ok; `ext_far` 1024 m windows, kmax 0.15, 100 m step, 500 m spacing, 5–20 km,
  2213 ok. Certified windows (empirical unc ≤ 0.5 m): 4726 + 1227.
- Combined (`forward_combined/`, 4465 windows, depth 7.2–27.5 m): SAR radial-centroid λ vs
  λ predicted from nearest-depth gauge: median +3.6 %, NMAD 20 % per window; per 1 m depth
  bin within ±5 % except AWAC-referenced bins 10–15 m (+8…+17 %: AWAC E(f) peaks at 10.8 s;
  with WR17 the same bins are within ±8 %) and 22.5–23 m (+13 %) / 27–28 m (−20 %, n=86).
  Using the 8 m-array spectrum offshore under-predicts (−10…−25 % beyond 12 m): reference
  spectrum must be local. Gauge choice (±10 %) dominates over bathymetry (≤ 1 %).

### 2026-09-22 — Whole-scene forward check on GRD (Level-1, ESA-focused)

- Same pipeline on GRDH `..._8C9F` (VV): `grd/ext_near` 512 m 0.25–6 km (5670 windows ok,
  3791 identifiable), `grd/ext_far` 1024 m 5–20 km (2157 ok, 1631 identifiable).
  `forward_lambda_check.py --min-depth` added (depth-sliced runs per gauge).
- Combined (`grd/forward_combined`, 4745 windows, 7.0–27.5 m):
  paper contour peak λ vs nearest-depth-gauge prediction: median +0.4 %, NMAD 16 %,
  p10/p90 −22/+21 % (SLC: −5.3 %, NMAD 21 %, p10 −59 %); radial centroid +8.8 %,
  NMAD 19 %. Per bin: 7–9 m +2…+6 %, 15–22 m +4…+8 %, AWAC-referenced 9–15 m
  +12…+25 %, 26–28 m ±15 %.
- Multilooking (ENL≈4–5) removes most spurious short-λ peaks of the single-look SLC.

### 2026-09-22 — Block39: audit fixes and confirmation run (SLC + GRD)

Fixes to the issues raised in the external audit of dd2f21d, then the whole-scene
forward check repeated from scratch on both products (`duck_frf/Block39_s1_paper_confirm`).

Code
- `s1_transect_bathy.py`: morphology on edge-replicated padding (the old
  `border_value=1` made both classes touch every border, so `--sea-side` degenerated
  to "largest component"); tie between candidate components now raises;
  `sea_side_contact_fraction` recorded. Window footprints from the outer pixel edges
  with the boundary densified every pixel (sea test applied to it too) instead of the
  3× subsampled interior grid. Spectral mask excludes only DC; the low-k cut moved to
  peak picking as `k >= --kmin-factor * pi / window` (default 4) with a
  `peak_at_kmin_edge` flag; `--parts-from` finalises stored partial spectra with a
  different factor.
- `s1_iw_annotation.GeoGrid` now raises `DeprecationWarning` (line-number geolocation,
  superseded by `s1_iw_geometry.SwathGeometry`).
- `frf_ground_truth.water_level(...)` + `--water-level-policy qc_only|preliminary`:
  the FRF `eopNoaaTide` reading at Duck is NOAA preliminary (`qc_unknown`,
  `representative_eligible False`), so it is no longer applied; band 3 is the NAVD88
  still-water depth and the rejected value (+0.235 m) goes into the error budget.
  New `rebuild_merged_bathymetry.py` re-runs the merge offline (no FRF budget).
- `forward_lambda_check.py`: `--sector-source sar|fixed --sector-bearing`, per-class
  bathymetry fractions and `dominant_source_class` per window, `block_bootstrap`
  (resamples whole spatial blocks: `--block-transects`, `--block-distance-m`),
  working `--chunk/--finalize`. `forward_lambda_combine.py`: `--primary-gauge`
  (predeclared gauge; nearest-in-depth kept as sensitivity), `--forward-template`,
  block-bootstrap CIs and the statistic split by dominant bathymetric source.
- New `coastline_check.py`: SAR waterline vs the DEM bed-elevation contour.

Results (bbox −75.79 36.15 −75.56 36.26, N=4, ground truth `..._ext20` rebuilt)
- Waterline: SAR vs DEM z = 0 contour, median +10 m seaward (NMAD 33 m, mask cell
  50 m); at z = +0.235 m (the rejected tide) +13.5 m. No systematic shift of the
  transect origin.
- Window acceptance with exact footprints: SLC near 5364 ok (was 5200), GRD near 5853
  (was 5670); far unchanged (2213 / 2218).
- kmin sweep (factor 2/3/4, same partial spectra): median λ identical for 3 and 4,
  factor 2 loses ~3 % of identifiable windows to low-k clutter; ≤ 1 % of identified
  peaks lie within half a bin of the cut. The cut is not driving the result.
- Primary result, gauge WR17 (FRF:waverider-17m) predeclared, paper contour peak,
  4706 (SLC) / 5000 (GRD) windows, 7.0–27.3 m, CI from a bootstrap over 53–62 spatial
  blocks: **GRD −0.8 % (CI −3.8…+2.3), SLC −4.8 % (CI −8.5…−1.2)**; p10/p90 −21/+20 %
  (GRD) vs −54/+17 % (SLC, single-look spurious short-λ peaks). Radial centroid
  +7.5 % (GRD) / +2.2 % (SLC).
- Gauge choice at aggregate level is minor: nearest-in-depth instead of WR17 moves the
  median by ≤ 0.6 % (it still matters inside AWAC-referenced depth bins).
- Directional sector: fixing it at the gauge bearing (72°) instead of the SAR maximum
  moves the radial centroid by ≤ 3 % and leaves the paper peak unchanged.
- Split by dominant bathymetric source (GRD, WR17): BlueTopo modern +2.8 %,
  nhatt-corrected legacy −2.3 % — a ~5 % source-dependent spread, larger than the
  ≤ 1 % quoted from the bias/NMAD analysis alone.
- Per 2 m depth bin (GRD): +8 % at 7–11 m, −5…+1 % at 11–23 m, −9 % at 25–29 m;
  SLC follows it except 17–19 m (−20 %) and 27–29 m (−38 %).

Tests: 359 pass. Pre-existing failures in this Linux device shell only
(`test_frf_block33.py`, `test_frf_operational.py`, `test_s1_iw_annotation.py`
credentials, `test_scene_selection.py`): temporary directories outside the repo and
file deletion not permitted in the shell — unrelated to these changes.
