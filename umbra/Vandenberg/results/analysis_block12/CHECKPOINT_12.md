# Checkpoint 12 - Sub-look dalla fase grezza: omega sale del 17%, il lobo si risolve

Data: 2026-09-01. Formazione 37.7 min, 165924 impulsi, nessuna decimazione.
32 sub-look disgiunti da 0.7044 s su 21.836 s di span, griglia a terra
1440 x 650 m a 5 m su `HAE = -36.376 m`, portante `+1`.

## Confronto diretto con Block 6

| grandezza | Block 6 (SICD, SVA/PFA) | Block 12 (retroproiezione) |
|---|---|---|
| lambda al picco | 130.79 m | **130.91 m** |
| omega | 0.3510 rad/s | **0.4121 rad/s** |
| T | 17.902 s | **15.248 s** |
| rapporto alla boa (0.4712 rad/s) | 0.745 | **0.874** |
| risposta alla dispersione sul lobo | 0.19 | **0.54** |
| supporto | 540 m, non tutto-acqua | 1440 m, tutto-acqua |
| span temporale | 11.589 s | 21.836 s |
| passo di fase adiacente | 0.407 rad | 0.290 rad |

La lunghezza d'onda si riproduce a **0.09%** attraverso due catene di
elaborazione completamente indipendenti. E' la validazione incrociata piu'
forte che abbiamo del lato spaziale.

`omega` sale del **17.4%** semplicemente sostituendo il prodotto focalizzato
del fornitore. L'elaborazione **costava** qualcosa. Non tutto, pero'.

## Il lobo ora e' risolto: c'e' una relazione di dispersione

22 bin superano i criteri (potenza > 0.15 del picco, R^2 > 0.97, coerenza
levigata > 0.25), coprendo `lambda` da **68.2 a 196.1 m** e `omega` da
**0.3002 a 0.7408 rad/s**. Su Block 6 questo era impossibile: il lobo
rispondeva alla dispersione solo al 19% e riportava lo stesso numero ovunque.

| modello | parametri | rms pesato [rad/s] |
|---|---|---|
| dispersione lineare, h libero | h = 7.105 m | 0.0326 |
| dispersione a h DEM + corrente | U = -3.221 m/s | 0.0330 |
| h libero + corrente | h = 12.03 m, U = -2.066 m/s | 0.0312 |
| scala pura su h DEM | 0.727 | 0.0310 |

Profondita' per bin: mediana **6.92 m**, IQR 6.43-7.81 m.
DEM sul supporto: p10 11.76, mediana 16.44, p90 23.03 m NAVD88.

**I quattro modelli si equivalgono entro il 5%.** Questi 22 bin non li
separano. In particolare una scala pura su `omega` produce una deriva della
profondita' per bin con la lunghezza d'onda, e quella deriva **c'e'**
(+3.12 m per e-fold): una profondita' fisica unica non e' stabilita.

## Cosa e' definitivamente chiuso

- **Ambiguita' di unwrapping.** Con 32 look il passo di fase adiacente e'
  0.290 rad, e sarebbe 0.332 rad al valore della boa. Nessuna vicinanza a pi.
- **Dipendenza dal baseline.** 496 coppie, tutte disgiunte per costruzione,
  da 0.649 a 21.836 s: pendenza di `omega` contro `dt` = **+0.0011 rad/s per s**.
  Piatta, come in Block 11 ma ora su un baseline doppio e senza apertura
  condivisa.
- **Elaborazione del fornitore.** SVA, PFA, pesatura, mappatura banda-tempo,
  Jacobiano di piano slant, quota di proiezione: tutto rimosso. Il residuo non
  puo' piu' essere attribuito a loro.

## Cosa resta aperto

`omega` e' ancora **12.6% sotto** la boa e **27% sotto** la dispersione alla
profondita' del DEM. La profondita' invertita e' 7.1 m contro un supporto che
il DEM colloca fra 11.8 e 23.0 m.

Le tre letture ancora in piedi, indistinguibili sui dati attuali:

1. la profondita' vera nella zona che domina il ritorno e' vicina a 7 m e il
   DEM mediano sul rettangolo non la rappresenta (il gradiente cross-shore e'
   -8.79 m/km, e il ritorno potrebbe essere dominato dal lato basso);
2. c'e' una corrente di **-2 / -3 m/s** lungo `k`. Fisicamente implausibile
   davanti a Vandenberg;
3. `omega` e' scalata di **0.727** da un meccanismo di imaging ancora non
   identificato.

## Difetto trovato e corretto

`analyze_block12_phase_slope.py` calcolava la coerenza da singole
realizzazioni spettrali, `|a conj(b)| / sqrt(|a|^2 |b|^2)`, che vale
identicamente uno. Il gate `--min-coherence` non filtrava nulla.
`analyze_block12_dispersion.py` la stima levigando cross- e auto-spettri su
un intorno 3x3 in `k` prima del rapporto. Con quella stima la coerenza al
picco vale **0.93 a 5.6 s** di separazione e **0.65 a 21.8 s**: la superficie
decorrela davvero sul dwell, ed e' un numero citabile in tesi.

## Prossimi passi

1. **Batimetria per sotto-patch.** Il supporto ha un gradiente di -8.79 m/km.
   Dividendolo lungo `k`, `omega` deve restare costante (invariante WKB) e
   `lambda` deve variare. Una prova su tre tratti da 480 m da' `omega` con
   dispersione +-11% e `lambda` +-25%, qualitativamente nel verso giusto ma
   troppo rumorosa: 480 m sono di nuovo solo 3.7 lunghezze d'onda. Serve una
   finestra scorrevole con sovrapposizione, non tre tagli netti.
2. **Confronto con lo spettro NDBC completo.** `T = 15.25 s` va cercato nello
   spettro della boa, non solo nel picco dominante a 13.33 s.
3. **Sweep sulla larghezza del look**, ora banale: i look si ricombinano
   sommando coerentemente i vicini, quindi da 32 si ottengono 16, 8, 4 senza
   riformare nulla.
