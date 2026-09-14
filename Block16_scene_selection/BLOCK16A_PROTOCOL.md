# Block16A protocol — frozen before catalog queries

## Scope and stop condition

Block16A builds a new metadata-only Umbra scene selector. It may list public S3
objects, retrieve STAC JSON, query small wave/buoy subsets, and read bounded
CPHD/SICD header/XML byte ranges. It must not download a complete CPHD, SICD,
SIDD or GEC; read a CPHD signal array or SICD pixels; form looks; correct a
frequency; run a dwell sweep; or invert bathymetry. Vandenberg and all Block8
and Block15 artifacts are immutable regression inputs. Work stops after the
shortlist and metadata audit.

The canonical builder is `code/run_block16a_scene_selection.py`; the two Block8
crawlers are historical and may only write below `Block8_validation`. They are
not permitted to write any Block16 path.

## Predeclared scientific design

The experiment seeks a *positive* validation of intensity cross-spectrum phase
to wave frequency. Block15H–K show that regular phase alone is insufficient,
nearby FFT bins can belong to one unresolved lobe, and fewer than one observed
cycle is a stress test rather than a clean validation. Therefore selection is
based on joint observability, not long period alone:

- catalog duration at least 15 s, preferably 20 s;
- at least three temporally disjoint looks;
- usable centre span divided by the applicable period at least 1.25 cycles,
  preferably 2.0 cycles;
- a preliminary wave-propagation/range-axis difference no larger than 15°,
  preferably 5°;
- spotlight CPHD and SICD from the same acquisition;
- a useful interior ocean ROI proxy, independent of whether a land control is
  also present;
- Category A additionally requires an independently measured, directional
  spectrum within 50 km and 1 h. Model output can support Category B only.

The 1.25-cycle hard threshold is deliberately above the frozen Vandenberg
matched value (~0.744 cycles), while still allowing finite public-catalog
dwell. The 2-cycle target supports a more stable signed slope. Three disjoint
looks are the minimum for a slope plus residual; overlapping sliding centres
are never counted as independent observations. A lobe must ultimately contain
at least four effective radial resolution elements, but catalog metadata cannot
establish `delta_eff`; spatial eligibility is thus explicitly provisional.

Directions reported “from” are converted to propagation “to” by adding 180°.
The visibility gate uses axial difference modulo 180°, while full 0–360°
directions are retained for later sign tests. STAC `view:azimuth` is only a
preliminary range axis; finalist geometry requires SICD/CPHD XML/PVP audit.

## Catalog and provenance protocol

Every run creates a new timestamped directory under
`Block16_scene_selection/catalog_snapshots/`. Listing, sidecar cache,
normalized processing table, acquisition table, errors and manifest are
written atomically. A snapshot is complete only when every listed STAC sidecar
was parsed. Incomplete crawls remain labelled `incomplete` and cannot replace
or feed the final catalog. Existing snapshots are never overwritten.

`umbra:collect_id` is the acquisition identifier. Processing variants are
retained and ranked by the frozen rule in `BLOCK16A_CONFIG.json`; missing IDs
receive a deterministic fallback key. Dates, durations, geometry, angles,
mode, asset consistency, channel aggregation and multistatic indicators are
audited before any oceanographic query. Anomalies remain in the audit table.

Natural Earth 1:10m land is only a preliminary coast mask. Its fraction and
interior-distance proxies cannot prove coast clearance at SAR scale. A clean
ocean ROI and an optional land control are distinct fields; 100% water receives
no automatic bonus.

## References, ranking and abstention

NDBC and CDIP discovery is automatic for all first-gate candidates; no scene
list or manual-verification bonus is allowed. Density, alpha1, alpha2, r1 and
r2, timestamp, units, monotonic frequencies, missing codes, Hm0, peak,
direction, concentration and competing systems are validated when available.
An active buoy without a directional spectrum is not a complete reference.

MFWAM/Open-Meteo is labelled
`screening_not_independent_validation`. Peak, mean and measured periods remain
separate; a missing model peak is not replaced silently by a mean. Category
gates precede ranking. Measured and model-only candidates use separate scores
within categories, followed by a small predeclared sensitivity check. No score
can compensate for a failed hard gate. If Category A is empty, the conclusion
is “no primary scene” without changing thresholds.

The byte-range phase is capped at 64 MiB total and five candidates. It may read
headers/XML and nine sparse PVP samples but never the CPHD signal or SICD image
pixels. Any exceeded budget stops the audit and is reported.

## Reproducibility

The canonical JSON serialization is UTF-8, sorted-key, compact JSON with a
trailing newline. Configuration SHA-256 is computed before ranking and stored
in the summary and delivery manifest. Offline tests require no network;
network integration checks are reported separately. All output hashes and
frozen Block8/Block15K hashes are recorded, and their post-run equality is a
delivery gate.
