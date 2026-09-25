# CHECKPOINT 42 — Deterministic footprint depths (Blocks 41–42)

Block directories:
- `duck_frf/Block41_depth_sampling/`
- `duck_frf/Block42_block40_depth_all/` (report: `duck_frf/Block42_block40_depth_all/BLOCK42_REPORT.md`)

HEAD at the start: `c817740`. No download, no catalogue query, no FRF request.

## What was established

1. **Environment.** Block40 is verified in the authoritative environment: 424 passed
   in `.venv-umbra-thesis`, after adding `pyproj` and handling artifact paths outside
   the working directory. The targeted tests for Blocks 40–41 pass (18).
2. **Depth-sampling defect.** Up to Block40 the forward λ prediction averaged over a
   random 60-depth subsample drawn from one generator per process. Results therefore
   depended on how runs were chunked. The default is now `--depth-sampling all`, which
   is deterministic.
3. **Effect.**
   - Aggregates move by only about 0.1–0.4 points: Block39 GRD −0.77 → −0.39 %,
     SLC −4.81 → −4.69 %.
   - Small strata move by several points. Band B GRD loses its significance: CI upper
     bound −0.9 → +8.9 %.
   - Band C GRD +1.38 → −0.21 %; band C SLC −7.76 % is unchanged.
4. **Conclusions of Block40 that hold.**
   - Opposite-sign compensation between sources, now stronger (0–12 m +8.5 / +13.8 %).
   - The SLC short-wavelength tail (30–39 % against 4.5 % for GRD).
   - The ladder is not monotone and does not converge to GRD.
   - Estimator offset +6.6/+6.8 %.
5. **Conclusion to rephrase.** The SLC − GRD gap in band C (7.5 points) is mostly a
   difference in window sets. On the 119 paired windows it is +4.1 points, with both
   medians compatible with zero.

## Frozen

- `--depth-sampling all` for every later forward check.
- Block40 is kept as published; Block42 supersedes its numbers.

## Open

- Regenerate Block42's `BLOCK40_SUMMARY.json` and manifest after the
  `block40_summary.py` change.
- Band A remains unvalidatable with the frozen protocol.
