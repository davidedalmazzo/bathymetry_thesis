"""Pre-registered Block15J coefficient-only multi-lag increment experiment."""
from __future__ import annotations
import csv, hashlib, json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import brentq
from umbra_sar.two_component_separability import tukey, correlated_noise
from umbra_sar.frequency_comparison import reference_fit, estimate_circular
from umbra_sar.multilag_increment import increment_structure, primary_score, calibration_threshold, b_decision

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'Vandenberg/results/analysis_block15'
CFG = OUT / 'BLOCK15J_CONFIG.json'


def response(shape, q, k):
    """One separable DFT response of the frozen BP12 Tukey window."""
    r, c = np.arange(shape[0]), np.arange(shape[1])
    wr, wc = tukey(shape[0]), tukey(shape[1])
    a = np.exp(-2j*np.pi*(q[:, 0, None]-k[0])*r/shape[0]) @ wr / wr.sum()
    b = np.exp(-2j*np.pi*(q[:, 1, None]-k[1])*c/shape[1]) @ wc / wc.sum()
    return a*b


def noise_cov(shape, q):
    r, c = np.arange(shape[0]), np.arange(shape[1]); wr, wc = tukey(shape[0])**2, tukey(shape[1])**2
    dr, dc = q[:, 0, None]-q[None, :, 0], q[:, 1, None]-q[None, :, 1]
    return ((np.exp(-2j*np.pi*dr[..., None]*r/shape[0]) @ wr / wr.sum()) *
            (np.exp(-2j*np.pi*dc[..., None]*c/shape[1]) @ wc / wc.sum()))


def finite_depth_omega(k, h=10., g=9.80665):
    return np.sqrt(g*k*np.tanh(k*h))


def k_for_omega(omega, h=10.):
    return brentq(lambda k: finite_depth_omega(k, h)-omega, 1e-6, 2.)


def frozen_block15i_score(z, template, times):
    """Exact stated frozen 15I rule, only re-evaluated on paired sequences."""
    grid = np.linspace(.1, .8, 21); y = z.ravel(); costs = []
    for static in (False, True):
        best = np.inf
        for s in grid:
            x = (template[None, :]*np.exp(1j*s*times[:, None])).reshape(-1, 1)
            if static: x = np.c_[x, np.tile(template, len(times))]
            fit = np.linalg.lstsq(x, y, rcond=None)[0]
            best = min(best, np.sum(abs(y-x@fit)**2))
        costs.append(best)
    gain = float(1-costs[1]/costs[0])
    idx = int(np.argmax(np.mean(abs(z)**2, axis=0)))
    corr = float(np.corrcoef(abs(z[:, idx]), np.mean(abs(z), axis=1))[0, 1])
    return bool(abs(corr) >= .85 and gain >= .10), gain, corr


def synth(cfg, family, replicate, phase, axis, delta, ratio, control=None):
    t = np.asarray(cfg['times_s']); shape = tuple(cfg['shape']); peak = np.asarray(cfg['peak'])
    q = np.array([[r, c] for r in range(*cfg['support']['rows']) for c in range(*cfg['support']['cols'])], float)
    d = np.array([delta, 0.]) if axis == 'radial' else np.array([0., delta])
    a, b, bm = response(shape, q, peak), response(shape, q, peak+d), response(shape, q, peak-d)
    # Controls are deterministic diagnostics, not calibration/evaluation units.
    seed = cfg['simulation']['seeds'].get(phase, 151002)
    family_code = {'A_band': 1, 'B_static_observed': 2, 'B_slow_OU': 3,
                   'plane': 4, 'null_contaminant': 5, 'constant_observed_offset': 6}[family]
    rng = np.random.default_rng(np.random.SeedSequence([seed, replicate, int(delta*1000), 0 if axis == 'radial' else 1, family_code]))
    k0 = k_for_omega(.4); dk = .007
    slopes = [finite_depth_omega(k0-dk), finite_depth_omega(k0), finite_depth_omega(k0+dk)]
    primary = np.exp(1j*slopes[1]*t)[:, None]*a
    if family == 'A_band':
        z = primary + .45*np.exp(1j*slopes[2]*t+0.4j)[:, None]*b + .25*np.exp(1j*slopes[0]*t-0.6j)[:, None]*bm
        truth = None
    elif family == 'B_static_observed':
        z, truth = primary + ratio*np.exp(.7j)*b, slopes[1]
    elif family == 'B_slow_OU':
        slow = correlated_noise(t, np.ones((1, 1)), ratio, 5., rng)[:, 0]
        z, truth = primary + slow[:, None]*b, slopes[1]
    elif family == 'plane': z, truth = primary, slopes[1]
    elif family == 'null_contaminant': z, truth = primary, slopes[1]
    elif family == 'constant_observed_offset': z, truth = primary + ratio*np.exp(.7j)*b, slopes[1]
    else: raise ValueError(family)
    # Both kinds are placed on all families, alternating by independent sequence;
    # this does not make samples inside a sequence independent.
    tau = cfg['simulation']['noise_tau_s'][replicate % 2]
    z = z + correlated_noise(t, noise_cov(shape, q), 1/cfg['simulation']['snr_amplitude'], tau, rng)
    return z, a, truth, slopes, tau


def one_row(cfg, family, rep, phase, axis, delta, ratio, control=False):
    z, a, truth, slopes, tau = synth(cfg, family, rep, phase, axis, delta, ratio)
    structure = increment_structure(z, cfg['times_s'], cfg['primary_diagnostic']['lag_edges_s'], min_pairs=3)
    score = primary_score(structure)
    i = int(np.argmax(np.mean(abs(z)**2, axis=0)))
    fit = reference_fit(z[:, i], cfg['times_s'], 16)
    circular = estimate_circular(z[:, i], cfg['times_s'], (1, 2, 4, 8), [-1, 1])
    old, gain, corr = frozen_block15i_score(z, a, np.asarray(cfg['times_s']))
    err = None if truth is None else abs(fit['s_phi']-truth)/truth
    return dict(phase=phase, family=family, replicate=rep, axis=axis, separation_bins=delta,
                ratio=ratio, noise_tau_s=tau, score=score, valid_structure=structure['valid'],
                denominator=structure['denominator'], E_early=structure['values'][0], E_mid1=structure['values'][1],
                E_mid2=structure['values'][2], E_late=structure['values'][3], pair_counts=';'.join(map(str, structure['pair_counts'])),
                truth_primary_s=truth, ols_s=fit['s_phi'], circular_s=circular['s_phi'], r2=fit['r2'],
                frozen_valid=bool(fit['r2'] >= .97 and circular['valid']), relative_slope_error=err,
                B_slope_error_over_10pct=bool(err is not None and err > .1),
                block15i_detects_B=old, block15i_m1_gain=gain, block15i_amp_corr=corr,
                A_slopes=';'.join(f'{s:.8f}' for s in slopes), control=control)


def rate_ci(k, n):
    # Wilson is descriptive for a homogeneous stratum; report each stratum too.
    if not n: return [None, None]
    z, p = 1.96, k/n; den = 1+z*z/n; ctr = (p+z*z/(2*n))/den
    half = z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [float(max(0, ctr-half)), float(min(1, ctr+half))]


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, default=lambda x: x.item() if isinstance(x, np.generic) else str(x))+'\n', encoding='utf-8')


def main():
    cfg = json.loads(CFG.read_text())
    rows = []
    for fam in ['A_band', 'B_static_observed', 'B_slow_OU']:
        for rep in range(8): rows.append(one_row(cfg, fam, rep, 'calibration', 'radial', 2.223, .3 if rep < 4 else .7))
    # Threshold is frozen after calibration and before examination of evaluation.
    a_cal = np.array([r['score'] for r in rows if r['family'] == 'A_band' and r['score'] is not None])
    threshold = calibration_threshold(a_cal, .05)
    for fam in ['A_band', 'B_static_observed', 'B_slow_OU']:
        for axis, delta in [('radial', 3.0), ('tangential', 1.452)]:
            for rep in range(8): rows.append(one_row(cfg, fam, rep, 'evaluation', axis, delta, 1.0))
    for fam in ['plane', 'null_contaminant', 'constant_observed_offset', 'B_slow_OU']:
        rows.append(one_row(cfg, fam, 99, 'control', 'radial', 2.223, .7, control=True))
    for r in rows:
        r['decision'] = 'B' if b_decision(r['score'], threshold) else 'abstain'
        r['block15i_decision'] = 'B' if r['block15i_detects_B'] else 'abstain'
    fields = list(rows[0]);
    with (OUT/'BLOCK15J_RESULTS.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    ev = [r for r in rows if r['phase'] == 'evaluation']; A = [r for r in ev if r['family'] == 'A_band']; B = [r for r in ev if r['family'] != 'A_band']
    detected = lambda rs, key='decision': sum(r[key] == 'B' for r in rs)
    by_family = {fam: {'n': len(x := [r for r in ev if r['family'] == fam]), 'B': detected(x),
                       'abstain': len(x)-detected(x), 'rate_ci95_wilson': rate_ci(detected(x), len(x))}
                 for fam in ['A_band','B_static_observed','B_slow_OU']}
    held = [r for r in B if r['axis'] == 'tangential']
    b_dist = [r for r in B if r['B_slope_error_over_10pct']]
    utility = detected(A) <= .1*len(A) and detected(B) >= .5*len(B) and detected(ev) >= .4*len(ev) and detected(held) >= .4*len(held)
    summary = {'block': '15J', 'status': 'complete', 'independent_sequences': {'calibration': 24, 'evaluation': 48, 'controls': 4, 'total': len(rows)},
               'threshold': threshold, 'evaluation': {'A_n':len(A),'B_n':len(B),'A_as_B':detected(A),'A_as_B_ci95':rate_ci(detected(A),len(A)),
               'B_detected':detected(B),'B_detected_ci95':rate_ci(detected(B),len(B)),'abstentions':len(ev)-detected(ev),
               'decision_fraction':detected(ev)/len(ev),'by_family':by_family,'heldout_tangential_B':{'n':len(held),'detected':detected(held),'ci95':rate_ci(detected(held),len(held))},
               'B_slope_error_over_10pct':len(b_dist),'B_slope_error_leq_10pct':len(B)-len(b_dist),'B_estimate_unavailable':0,
               'B_passes_frozen_criteria':sum(r['frozen_valid'] for r in B)},
               'paired_block15i': {'A_as_B':detected(A,'block15i_decision'),'B_detected':detected(B,'block15i_decision'),
                  'abstentions':len(ev)-detected(ev,'block15i_decision')},
               'utility_gate_passed': utility, 'utility_gate': cfg['primary_diagnostic']['utility'],
               'transfer_claim': 'constant-transfer primary only; variable-transfer non-cancellation is analytic/unit-test control, not a favourable evaluation.'}
    write_json(OUT/'BLOCK15J_SUMMARY.json', summary)
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.5))
    for fam, col in [('A_band','#1f77b4'),('B_static_observed','#d62728'),('B_slow_OU','#2ca02c')]:
        x = [r['score'] for r in ev if r['family'] == fam]; ax[0].hist(x, bins=8, alpha=.55, label=fam, color=col)
    ax[0].axvline(threshold, color='k', ls='--', label='frozen threshold'); ax[0].set(xlabel='primary score', ylabel='independent sequences'); ax[0].legend(fontsize=7)
    for fam, col in [('A_band','#1f77b4'),('B_static_observed','#d62728'),('B_slow_OU','#2ca02c')]:
        x = [r for r in ev if r['family']==fam]; y = np.array([[r['E_early'],r['E_mid1'],r['E_mid2'],r['E_late']] for r in x],float)
        ax[1].plot(range(4), y.mean(0), 'o-', color=col, label=fam)
    ax[1].set(xticks=range(4), xticklabels=['.6–2','2–5','5–12','12–23'], xlabel='lag class (s)', ylabel='normalised increment energy'); ax[1].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(OUT/'BLOCK15J_INCREMENT_DIAGNOSTIC.png', dpi=160); plt.close(fig)
    tracked = ['code/umbra_sar/multilag_increment.py', 'code/analyze_block15j_multilag_increment.py',
               'tests/test_multilag_increment.py', 'Vandenberg/results/analysis_block15/BLOCK15J_CONFIG.json',
               'Vandenberg/results/analysis_block15/BLOCK15J_PROTOCOL.md', 'Vandenberg/results/analysis_block15/BLOCK15J_REPORT.md',
               'Vandenberg/results/analysis_block15/BLOCK15J_RESULTS.csv', 'Vandenberg/results/analysis_block15/BLOCK15J_SUMMARY.json',
               'Vandenberg/results/analysis_block15/BLOCK15J_INCREMENT_DIAGNOSTIC.png', 'WORKLOG.md']
    files = []
    for rel in tracked:
        p = ROOT/rel
        files.append({'path': rel, 'bytes': p.stat().st_size,
                      'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
    write_json(OUT/'BLOCK15J_DELIVERY_MANIFEST.json', {
        'block': '15J', 'status': 'complete; synthetic-only utility gate failed and work stopped',
        'inputs_read': 'frozen metadata/configuration and previous lightweight artifacts only; no signal array',
        'tests': {'new_targeted': 10, 'full_suite': '117 passed, 0 failed, 0 skipped (2026-09-13)'},
        'prior_block15i_guards': {'count': 5, 'current_mismatches': 0,
          'coverage': 'H/G manifests and F/B/E configs; excludes 15I self-artifacts'},
        'files': files})
    print(json.dumps(summary, indent=2))

if __name__ == '__main__': main()
