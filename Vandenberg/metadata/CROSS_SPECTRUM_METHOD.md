# Cross-spectrum domain and convention

## Chosen object

The Block-3 ocean-wave cross-spectrum is computed from **intensity images
derived from the complex Doppler sub-looks**, not directly from the mutually
disjoint complex look fields.

The complex sub-looks remain the master products. For each look (m):

1. retain complex (z_m(x,y));
2. derive (I_m(x,y)=|z_m(x,y)|^2);
3. remove one global spatial plane and apply the documented 2-D Tukey window;
4. calculate (F_m(k)=\mathcal{F}_{2D}\{I_m\});
5. calculate each ordered cross-spectrum as
   (C_{s,r}(k)=F_s(k)F_r(k)^*\).

Thus pair `1-2` means reference look 1 and secondary look 2:
`F_2 * conj(F_1)`.

## Primary-method basis

Li, Mouche, Stopa & Chapron (2019), *Journal of Geophysical Research: Oceans*,
section 2.2.1, describes the sequence used here: FFT of SLC tiles, division of
the azimuth spectrum into three nonoverlapping parts, inverse transformation to
sub-look intensity images, and subsequent image co-/cross-spectrum formation.

- DOI: `10.1029/2018JC014638`
- Source: https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2018JC014638
- Foundational method cited there: Engen & Johnsen (1995),
  DOI `10.1109/36.406690`.

The present implementation deliberately differs in one conservative detail:
it does **not** crop a small azimuth tile before the Doppler split. It transforms
all 107,800 SICD azimuth columns for each selected range row, then crops the ROI.

## Interpretation limits in Block 3

- Phase closure is checked as
  `phi13 = wrap(phi12 + phi23)` at one identical spatial-frequency bin.
- A locally smoothed phase and local magnitude-squared coherence are also
  reported; smoothing means its closure need not be exact algebraically.
- No cross phase is converted to a physical period.
- No `T_SAR` is declared.
- Land-control shifts and phase ramps are reported without silently removing
  them from the ocean products.
