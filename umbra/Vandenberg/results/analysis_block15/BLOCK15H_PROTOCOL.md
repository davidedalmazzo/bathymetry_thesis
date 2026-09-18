# Block15H protocol frozen before BP12 audit

Input is only `block12_backprojection/BLOCK12_SUBLOOKS_complex64.npy` plus its
manifest and small Block15 artifacts. The existing 32 BP12 looks are read-only;
no CPHD/SICD signal array is opened.

The fixed representative is `[133,65]`. The declared neighborhood is rows
`127:140`, columns `59:72`; it is an audit support, never a peak search.
Preprocessing is copied from Block15B: intensity, global-plane detrend,
separable Tukey alpha 0.1 and shifted unpadded FFT. Signed temporal estimates
reuse Block15B `reference_fit` relative to look 16. Cross-product convention is
unchanged: `F_secondary * conj(F_reference)`.

Two resolution scales are reported: FFT-bin spacing and explicit-window power
kernel width. A third, conservative empirical scale is the local BP12 lobe
FWHM through the fixed bin. Neighbor-bin statistics are descriptive; neither
bins, conjugates, nor 32 common-look slopes are independent samples.

Five deterministic coefficient-only checks use the same grid/window/times:
isolated lobe; two lobes separated by 6 bins; two separated by 1 bin; off-grid
single lobe; weak 1.5-bin component. They calibrate procedure behavior only and
do not tune to BP12 or alter a real frequency.
