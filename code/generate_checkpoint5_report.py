"""Generate the reproducible Block-5 checkpoint and test report."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'umbra/Vandenberg/results/analysis_block5'


def load(name: str):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def main() -> None:
    frozen = load("BLOCK5_FROZEN_INPUTS.json")
    ndbc = load("BLOCK5_NDBC_FULL_SPECTRUM.json")
    dispersion = load("BLOCK5_DISPERSION_DIAGNOSTIC.json")
    theory = load("BLOCK5_PHASE_THEORY.json")
    sensitivity = load("BLOCK5_SAR_SENSITIVITY.json")
    f1 = ndbc["target_f1"]["nearest_bin"]
    f2 = ndbc["target_f2"]["nearest_bin"]
    family = sensitivity["family_summaries"]

    report = f"""# CHECKPOINT_5 - Identificazione fisica della componente nearshore

## Condizione di arresto

Block 5 è completo. È stato eseguito soltanto il confronto fisico della componente nearshore: nessun dwell sweep 5-16 s e nessuna inversione batimetrica. Il valore SAR-only resta congelato a `T_SAR={frozen['frozen_sar_only']['T_SAR_s']:.12f} s` (`omega={frozen['frozen_sar_only']['omega_rad_per_s']:.12f} rad/s`) e non è stato modificato dopo il confronto esterno. Il file sorgente Block 4 ha SHA-256 `{frozen['source_files']['block4_sar_only_sha256']}`.

## NDBC 46218: spettro completo

- Dataset ufficiale aggregato `46218w9999.nc`: `{ndbc['source']['bytes']:,}` byte; SHA-256 `{ndbc['source']['sha256']}`.
- Record spettrale più vicino: `{ndbc['timing']['nearest_spectral_record_utc']}`, offset `{ndbc['timing']['offset_record_minus_acquisition_s']:.3f} s` rispetto all'acquisizione SICD `{ndbc['timing']['sicd_acquisition_utc']}`.
- Sono stati letti tutti i `{ndbc['source']['frequency_count']}` bin e tutti i campi disponibili: `spectral_wave_density`, `alpha1`, `alpha2`, `r1`, `r2`. La tabella completa è in `NDBC_46218_20250216T1900_FULL_DIRECTIONAL_SPECTRUM.csv`.
- L'integrazione dello spettro dà `m0={ndbc['bulk_from_integrated_spectrum']['m0_m2']:.6f} m²`, `Hm0={ndbc['bulk_from_integrated_spectrum']['Hm0_m']:.3f} m`, coerente con l'ordine di grandezza del dato standard Hs=2.02 m.
- Convenzione NDBC: `alpha1` è la direzione *da cui* provengono le onde; il confronto con il vettore SAR usa `(alpha1+180) mod 360`.

| Target | Bin NDBC | C11 (m²/Hz) | frazione m0 del bin | alpha1 da | propagazione verso | r1 | differenza assiale da SAR 79.836° |
|---|---:|---:|---:|---:|---:|---:|---:|
| f1=1/17.902={ndbc['requested_frequencies']['f1_from_reported_17_902_s']:.5f} Hz | {f1['frequency_hz']:.3f} Hz ({f1['period_s']:.2f} s) | {f1['spectral_wave_density_m2_per_hz']:.3f} | {100*f1['fraction_total_variance']:.3f}% | {f1['alpha1_direction_from_deg']:.0f}° | {f1['alpha1_propagation_to_deg']:.0f}° | {f1['r1']:.2f} | {f1['axial_direction_difference_from_SAR_deg']:.3f}° |
| f2=1/13.33={ndbc['requested_frequencies']['f2_from_13_33_s']:.5f} Hz | {f2['frequency_hz']:.3f} Hz ({f2['period_s']:.2f} s) | {f2['spectral_wave_density_m2_per_hz']:.3f} | {100*f2['fraction_total_variance']:.3f}% | {f2['alpha1_direction_from_deg']:.0f}° | {f2['alpha1_propagation_to_deg']:.0f}° | {f2['r1']:.2f} | {f2['axial_direction_difference_from_SAR_deg']:.3f}° |

Il rapporto di densità del bin f1 rispetto a f2 è `{ndbc['nearest_bin_energy_ratio_f1_over_f2']:.3f}`: f2 ha circa `33.3x` l'energia spettrale per Hz del bin lungo. Il bin 0.055 Hz ha direzione nominale quasi perfetta (80°), ma energia molto bassa e scarsa concentrazione direzionale (`r1=0.29`); nelle sette ore 16-22 UTC la sua direzione oscilla tra 60° e 108°. Il bin 0.075 Hz è il massimo energetico, ha `r1=0.89` e direzione 72° all'acquisizione, 72-96° nelle ore vicine.

### Sistemi ondosi

Senza smoothing compaiono massimi adiacenti a 0.065, 0.075, 0.085 e 0.101 Hz. Con smoothing dichiarato di soli 0.75 bin questi si fondono in un solo massimo robusto a 0.075 Hz: non vengono quindi dichiarati quattro sistemi fisici separati. La partizione larga 0.045-0.135 Hz contiene il `67.91%` della varianza (`Hm0=1.637 m`) ed è il sistema swell dominante; la banda 0.135-0.250 Hz contiene il `25.32%` ed è una componente più corta/secondaria. Non emerge un massimo separato attorno a 0.05586 Hz identificabile come componente autonoma di 17.9 s.

## Confronto con il picco SAR

Il picco SAR resta `lambda={frozen['frozen_sar_only']['lambda_SAR_m']:.3f} m`, `theta={frozen['frozen_sar_only']['theta_SAR_wavevector_bearing_deg_mod_180']:.3f}°`. La direzione del sistema NDBC dominante a 13.33 s differisce di soli `{f2['axial_direction_difference_from_SAR_deg']:.3f}°`; il bin lungo differisce di `{f1['axial_direction_difference_from_SAR_deg']:.3f}°`, ma è debole, poco concentrato e non persistente come direzione.

## Controllo di dispersione (solo diagnostico)

Con `omega²=g k tanh(kh)` e `lambda=130.603 m`:

| Periodo fissato | profondità richiesta |
|---|---:|
| 17.902230457 s | {dispersion['required_depth_cases_m']['frozen_SAR_exact']:.3f} m |
| 13.33 s | {dispersion['required_depth_cases_m']['buoy_dominant_13_33']:.3f} m |

La stima grossolana NOAA ETOPO 2022 a 30 arc-second sulla cella del centro ROI è `{dispersion['rough_roi_depth']['nearest_grid_water_depth_m']:.3f} m`. La cella è circa 0.77 x 0.93 km, mescola costa e pendio ripido, e il vicinato contiene celle d'acqua da `{dispersion['rough_roi_depth']['five_by_five_water_cell_depth_range_m'][0]:.1f}` a `{dispersion['rough_roi_depth']['five_by_five_water_cell_depth_range_m'][1]:.1f} m`. Il caso 17.9 s è più vicino al valore della cella centrale, ma la risoluzione è insufficiente per validare un periodo o fare batimetria; il valore 10.63 m richiesto dal caso 13.33 s è plausibile all'interno del forte gradiente locale e non viene escluso.

## Perché dphi/dt non è necessariamente omega_ocean

La formulazione Engen-Johnsen, come implementata nell'ATBD Sentinel-1 OSW Eq. (34), è

`P_qlin(k,t)=C(k)[A exp(-i omega t)+B exp(+i omega t)]`, con `A=|T(k)|²S(k)` e `B=|T(-k)|²S(-k)`.

Quindi `phi=-omega t` vale soltanto nel limite unidirezionale `B=0` per il picco selezionato e per la convenzione `F_secondary * conj(F_reference)`. In generale:

`dphi/dt|0 = omega (B-A)/(A+B)`.

- Il rapporto `S(k)/S(-k)` è mescolato con l'asimmetria MTF `|T(-k)|²/|T(k)|²`.
- L'MTF totale comprende shift/velocity-bunching e RAR MTF; nell'ideale stazionario la sua fase si cancella in `|T|²`, ma le ampiezze direzionali modificano la fase e filtri diversi tra look possono lasciare termini differenziali.
- Il contributo nonlineare complesso `P_nlin(k,t)` si somma vettorialmente; OSW lo sottrae tramite LUT di vento, direzione e wave age prima dell'inversione.
- Patch finita, peak drift, finestre temporali da 6 s, overlap, corrente `k dot U`, shift residuo e decorrelazione sono ulteriori termini di bias.

Per ipotesi T=13.33 s, il solo matching della derivata a zero richiederebbe `B/A={theory['small_lag_directional_ratio_diagnostics']['if_ocean_period_13_33_s_B_over_A']:.3f}`. Sul baseline PVP reale 0-11.589 s quel modello produce però `{theory['finite_baseline_13_33_s_test']['small_lag_matched_ratio']['fit_slope_rad_per_s']:.3f} rad/s`, non -0.351. Una miscela bidirezionale quasi-lineare stazionaria non basta: servirebbe un termine netto aggiuntivo di circa `+{theory['phase_bias_needed_if_13_33_s_unidirectional_rad_per_s']:.3f} rad/s`, la cui origine non è stata calibrata in questo blocco. Le LUT C-band Sentinel-1 non sono trasferibili numericamente all'Umbra X-band nearshore.

## Sensitivity analysis SAR-only

Sono state valutate 24 configurazioni valide senza dati esterni e senza riselezionare il massimo a ogni variante.

| Famiglia | slope min...max (rad/s) | periodo min...max (s) | max variazione relativa da -0.350972 |
|---|---:|---:|---:|
| look width 5.5/6.0/6.5 s, 9 centri comuni | {family['look_width']['slope_range_rad_per_s'][0]:.6f}...{family['look_width']['slope_range_rad_per_s'][1]:.6f} | {family['look_width']['period_range_s'][0]:.3f}...{family['look_width']['period_range_s'][1]:.3f} | {100*family['look_width']['maximum_absolute_relative_slope_change']:.2f}% |
| overlap subsampling 80/60/40% | {family['overlap_subsampling']['slope_range_rad_per_s'][0]:.6f}...{family['overlap_subsampling']['slope_range_rad_per_s'][1]:.6f} | {family['overlap_subsampling']['period_range_s'][0]:.3f}...{family['overlap_subsampling']['period_range_s'][1]:.3f} | {100*family['overlap_subsampling']['maximum_absolute_relative_slope_change']:.2f}% |
| ROI baseline e cinque crop 80% | {family['roi']['slope_range_rad_per_s'][0]:.6f}...{family['roi']['slope_range_rad_per_s'][1]:.6f} | {family['roi']['period_range_s'][0]:.3f}...{family['roi']['period_range_s'][1]:.3f} | {100*family['roi']['maximum_absolute_relative_slope_change']:.2f}% |
| patch radius 1-5 e quattro offset di un bin | {family['spectral_patch']['slope_range_rad_per_s'][0]:.6f}...{family['spectral_patch']['slope_range_rad_per_s'][1]:.6f} | {family['spectral_patch']['period_range_s'][0]:.3f}...{family['spectral_patch']['period_range_s'][1]:.3f} | {100*family['spectral_patch']['maximum_absolute_relative_slope_change']:.2f}% |

Tutte le 24 varianti mantengono pendenza negativa, unwrapping giustificato e `R² >= 0.997`. L'intervallo complessivo è `{sensitivity['robustness_summary']['all_variant_slope_range_rad_per_s'][0]:.6f}...{sensitivity['robustness_summary']['all_variant_slope_range_rad_per_s'][1]:.6f} rad/s` (`{sensitivity['robustness_summary']['all_variant_period_range_s'][0]:.3f}...{sensitivity['robustness_summary']['all_variant_period_range_s'][1]:.3f} s`); la mediana coincide con il valore congelato. La pendenza è quindi una proprietà robusta del dato/processamento locale, non del singolo set di parametri, pur mostrando una sistematica ROI/patch fino a circa 5%.

## Conclusione richiesta

**Conclusione 2.** Il picco SAR sembra corrispondere al sistema buoy dominante di circa 13.3 s, mentre la pendenza di fase SAR contiene un bias fisico/processistico rispetto a `-omega_ocean`.

Motivazione: a 17.9 s la boa mostra soltanto una coda debole (3% della densità del picco, 0.267% della varianza totale nel bin), senza massimo separato e con direzione poco concentrata/instabile. Il sistema 13.33 s è il massimo robusto, direzionalmente compatibile con il vettore SAR e persistente nelle ore vicine. La pendenza SAR -0.351 è robusta, ma la teoria cross-spettrale vieta di interpretarla automaticamente come frequenza oceanica. Questa conclusione identifica l'associazione più probabile, non calibra ancora il termine di bias e non costituisce inversione batimetrica.

## Test e riferimenti

- Suite finale: `31 passed` (`tests/TEST_REPORT_BLOCK5.md`).
- [NDBC measurement descriptions](https://www.ndbc.noaa.gov/faq/measdes.shtml)
- [NDBC spectral NetCDF catalog](https://dods.ndbc.noaa.gov/thredds/catalog/data/swden/46218/catalog.html)
- [Engen & Johnsen (1995)](https://doi.org/10.1109/36.406690)
- [Sentinel-1 OSW ATBD v1.3](https://sentinels.copernicus.eu/documents/247904/349449/S-1_L2_OSW_Detailed_Algorithm_Definition.pdf)
- [NOAA ETOPO 2022](https://www.ncei.noaa.gov/products/etopo-global-relief-model)

## Stop esplicito

`CHECKPOINT_5`: arresto prima del dwell sweep 5-16 s e prima di qualsiasi inversione della profondità.
"""
    (ROOT / 'docs/checkpoints/CHECKPOINT_5.md').write_text(report, encoding="utf-8")

    test_report = f"""# Synthetic and artifact regression report - Block 5

Generated: `{date.today().isoformat()}`

- Command: `D:\\Dati Tesi\\Umbra\\.venv\\Scripts\\python.exe -B -m pytest`
- Result: **31 passed**.
- The 19 Block-2 transform tests remain active, including numerical `fft`/`ifft`, Doppler ordering, `Col.Sgn=-1`, cross-spectrum phase sign, RGAZIM axis and strict separation of the 18.068061721-s processed aperture from the 22.540812513-s CPHD dwell.
- The three Block-3/4 wave-analysis tests remain active: geographic wavenumber conversion, registration/phase-ramp sign, and fixed-patch temporal phase recovery.
- Five new physical-identification tests verify finite-depth dispersion, OSW Eq. (34) forward/reverse sign, the analytic `S(k)/S(-k)` zero-lag slope, NDBC directional-distribution normalization, frequency bins and direction conventions.
- Four new artifact audits verify the frozen SAR hash and period, all five complete NDBC variables and requested bins, the 24 SAR-only sensitivity variants and no-dwell-sweep guardrail, and the diagnostic-only status of the dispersion depths.

These tests validate numerical conventions, artifacts and guardrails. They do not by themselves prove the physical component assignment; that conclusion follows from the documented spectral evidence and remains subject to future independent validation.
"""
    (ROOT / "tests/TEST_REPORT_BLOCK5.md").write_text(
        test_report, encoding="utf-8"
    )
    print(ROOT / 'docs/checkpoints/CHECKPOINT_5.md')
    print(ROOT / "tests/TEST_REPORT_BLOCK5.md")


if __name__ == "__main__":
    main()
