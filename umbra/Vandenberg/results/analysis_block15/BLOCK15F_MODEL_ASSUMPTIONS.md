# Block15F — modello di trasferimento: ambito e assunzioni

## Oggetto modellato

`H_j(k)` moltiplica il coefficiente di una componente di elevazione nel dominio Fourier dell'intensità BP12. Non è la fase complessa del sub-look radar, non è altezza d'onda misurata e non è un MTF X-band calibrato. Con `eta=Re{A exp(i(k.x-omega t))}`, il modello numerico limitato è `H=T_t+T_vb`; `T_h=0`.

## Termini

| Termine | Formula usata | Unità di H | Fonte locale e validità |
|---|---|---:|---|
| Tilt/RAR `T_t` | `-2 i tan(i) k_LOS` | m^-1 | Linearizzazione del proxy `(n.LOS/cos i)^2` nel forward model Block10 (`ocean_sar_forward.py`). Geometrico; non è un MTF Bragg calibrato. |
| Idrodinamico `T_h` | non implementato, quindi 0 | m^-1 | Block10 dichiara assente la modulazione idrodinamica. Block5/6 ricordano che i parametri OSW/Engen-Johnsen C-band non sono trasferibili numericamente a Umbra X-band nearshore. Nessun parametro locale di rilassamento/backscatter verificato. |
| Velocity bunching `T_vb` | `-(i R/V) k_f U_LOS/eta` | m^-1 | Linearizzazione della densità/Jacobiano per `y'=y+(R/V)u_LOS`, coerente con la mappa conservativa Block10. `U_LOS/eta=sin(i) omega coth(kh) (khat.los_h)-i cos(i)omega`. |

La velocità orizzontale usa coerentemente `a omega coth(kh)` e la verticale `a omega`; non si usa la bozza acqua-profonda insieme a `coth(kh)`. `R/V` è ricavato PVP look per look. La formula broadside non è dichiarata esatta: `k_f` è proiettato sulla direzione di volo effettiva, separata dalla LOS orizzontale e dagli assi BP12. Il modello non somma una seconda displacement/shift MTF: farlo duplicerebbe velocity bunching.

## Limiti fisici

La linearizzazione non rappresenta folding/caustiche; vicinanza a `H=0` renderebbe arg(H) instabile e diminuirebbe osservabilità. L'ampiezza del coefficiente SAR non viene convertita in elevazione: non vengono usati Jacobiano o ampiezza orbitale come filtri sui dati reali. Sono assunzioni esplicite gli scenari `(T=13.33 s,h=5/10/20 m)` e `(T=17.902230457 s,h=10 m)`: non sono profondità o periodi misurati; 13.33 s è solo associazione diagnostica esterna e 17.902230457 s resta congelato SAR-only.

## Convenzione di fase

Per `z_j=A H_j exp(i s_wave t_j)` e il cross adottato `z_j conj(z_r)`, `arg=cross=s_wave(t_j-t_r)+arg(H_j conj(H_r))`. Se H è costante la seconda differenza è zero esattamente. Invertire riferimento/secondario o coniugare il lobo inverte il segno di entrambe le pendenze.

## Fonti locali consultate

- `code/umbra_sar/ocean_sar_forward.py`, Block10, formule esplicite per dispersione finita, velocità orbitale e mappa `y_SAR=y+(R/V)u_LOS`.
- `Block10_validation/results/CHECKPOINT_10.md`, limiti del modello (assenza MTF idrodinamico, raw phase history e two-scale Bragg).
- `code/analyze_block5_phase_theory.py` e `code/analyze_block6_phase_slope_map.py`, struttura Engen-Johnsen/OSW e avvertimento contro il trasferimento numerico C-band/X-band.

Nessuna formula non verificata è stata trasformata in correzione numerica.
