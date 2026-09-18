# Block29 — frozen phase A protocol

Same Samoa acquisition, no frozen artifact changes. Reuse Block28 identity,
SICD/PFA XML, CPHD header/XML, full ROI and verified buoy payload. Retrieve
only the compact complete PVP block (8,165,216 bytes), after a relevant HEAD
probe and size/ETag verification. No support/signal array. Structured dtype
from official SarPy CPHD XML, big-endian and integer SIGNAL/PulseNumber.

Reconstruct bistatic phase-gradient vectors, project along focus-plane normal
onto the declared PFA image plane, retain both Row and Col (cycles/metre),
compare angle against metadata PolarAngPoly and the independent SICD ARP.
Invert angle = atan2(k_col,k_row) separately at three Row carrier frequencies
and ROI representative points. Scene-interaction time from Tx/Rcv paths;
record clock conventions and TxTime/RcvTime differences. Rectangular output-k
and uniform-time centers are geometry-only weight cases, not exact vendor
illumination kernels. Unknown interpolation/antenna/pulse weights remain a
limitation and cannot be fitted to buoy agreement.

Thresholds in CONFIG are frozen before new PVP processing. Differential
baseline and duration sensitivity, absolute center variation, monotonicity,
gaps, geometry/poly equivalent timing and frequency support must pass. Reject
or mark conditional if spatial/radial coupling exceeds these limits. PASS
alone authorizes one resumable SICD download; otherwise record the impediment
and stop, without alternate formation. No q/bathymetry/boa optimization.

Numerical tests: structured offsets, units, inverse-transpose wavevector,
FFT sign/conjugate intensity lobes/cross convention, mask-domain synthetic
static/dynamic diagnostics (not a raw SAR simulator), byte-range guard and
frozen provenance. Full project-local pytest suite required.
