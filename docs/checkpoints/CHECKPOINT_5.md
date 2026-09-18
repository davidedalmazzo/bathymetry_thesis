# CHECKPOINT_5 - Identificazione fisica della componente nearshore

## Condizione di arresto

Block 5 è completo. È stato eseguito soltanto il confronto fisico della componente nearshore: nessun dwell sweep 5-16 s e nessuna inversione batimetrica. Il valore SAR-only resta congelato a `T_SAR=17.902230457045 s` (`omega=-0.350972205517 rad/s`) e non è stato modificato dopo il confronto esterno. Il file sorgente Block 4 ha SHA-256 `c399af008e2159ede9b6e27b8bf99dffdd17b7f808aa263ea569d20438df8fcd`.

## NDBC 46218: spettro completo

- Dataset ufficiale aggregato `46218w9999.nc`: `153,486,944` byte; SHA-256 `eb296c36049de144043c1a8b39a59df1ebeb50453541d23a0a784badcee0d20d`.
- Record spettrale più vicino: `2025-02-16T19:00:00+00:00`, offset `255.726 s` rispetto all'acquisizione SICD `2025-02-16T18:55:44.274000+00:00`.
- Sono stati letti tutti i `64` bin e tutti i campi disponibili: `spectral_wave_density`, `alpha1`, `alpha2`, `r1`, `r2`. La tabella completa è in `NDBC_46218_20250216T1900_FULL_DIRECTIONAL_SPECTRUM.csv`.
- L'integrazione dello spettro dà `m0=0.246774 m²`, `Hm0=1.987 m`, coerente con l'ordine di grandezza del dato standard Hs=2.02 m.
- Convenzione NDBC: `alpha1` è la direzione *da cui* provengono le onde; il confronto con il vettore SAR usa `(alpha1+180) mod 360`.

| Target | Bin NDBC | C11 (m²/Hz) | frazione m0 del bin | alpha1 da | propagazione verso | r1 | differenza assiale da SAR 79.836° |
|---|---:|---:|---:|---:|---:|---:|---:|
| f1=1/17.902=0.05586 Hz | 0.055 Hz (18.18 s) | 0.132 | 0.267% | 260° | 80° | 0.29 | 0.164° |
| f2=1/13.33=0.07502 Hz | 0.075 Hz (13.33 s) | 4.400 | 8.915% | 252° | 72° | 0.89 | 7.836° |

Il rapporto di densità del bin f1 rispetto a f2 è `0.030`: f2 ha circa `33.3x` l'energia spettrale per Hz del bin lungo. Il bin 0.055 Hz ha direzione nominale quasi perfetta (80°), ma energia molto bassa e scarsa concentrazione direzionale (`r1=0.29`); nelle sette ore 16-22 UTC la sua direzione oscilla tra 60° e 108°. Il bin 0.075 Hz è il massimo energetico, ha `r1=0.89` e direzione 72° all'acquisizione, 72-96° nelle ore vicine.

### Sistemi ondosi

Senza smoothing compaiono massimi adiacenti a 0.065, 0.075, 0.085 e 0.101 Hz. Con smoothing dichiarato di soli 0.75 bin questi si fondono in un solo massimo robusto a 0.075 Hz: non vengono quindi dichiarati quattro sistemi fisici separati. La partizione larga 0.045-0.135 Hz contiene il `67.91%` della varianza (`Hm0=1.637 m`) ed è il sistema swell dominante; la banda 0.135-0.250 Hz contiene il `25.32%` ed è una componente più corta/secondaria. Non emerge un massimo separato attorno a 0.05586 Hz identificabile come componente autonoma di 17.9 s.

## Confronto con il picco SAR

Il picco SAR resta `lambda=130.603 m`, `theta=79.836°`. La direzione del sistema NDBC dominante a 13.33 s differisce di soli `7.836°`; il bin lungo differisce di `0.164°`, ma è debole, poco concentrato e non persistente come direzione.

## Controllo di dispersione (solo diagnostico)

Con `omega²=g k tanh(kh)` e `lambda=130.603 m`:

| Periodo fissato | profondità richiesta |
|---|---:|
| 17.902230457 s | 5.556 m |
| 13.33 s | 10.627 m |

La stima grossolana NOAA ETOPO 2022 a 30 arc-second sulla cella del centro ROI è `3.227 m`. La cella è circa 0.77 x 0.93 km, mescola costa e pendio ripido, e il vicinato contiene celle d'acqua da `2.5` a `36.0 m`. Il caso 17.9 s è più vicino al valore della cella centrale, ma la risoluzione è insufficiente per validare un periodo o fare batimetria; il valore 10.63 m richiesto dal caso 13.33 s è plausibile all'interno del forte gradiente locale e non viene escluso.

## Perché dphi/dt non è necessariamente omega_ocean

La formulazione Engen-Johnsen, come implementata nell'ATBD Sentinel-1 OSW Eq. (34), è

`P_qlin(k,t)=C(k)[A exp(-i omega t)+B exp(+i omega t)]`, con `A=|T(k)|²S(k)` e `B=|T(-k)|²S(-k)`.

Quindi `phi=-omega t` vale soltanto nel limite unidirezionale `B=0` per il picco selezionato e per la convenzione `F_secondary * conj(F_reference)`. In generale:

`dphi/dt|0 = omega (B-A)/(A+B)`.

- Il rapporto `S(k)/S(-k)` è mescolato con l'asimmetria MTF `|T(-k)|²/|T(k)|²`.
- L'MTF totale comprende shift/velocity-bunching e RAR MTF; nell'ideale stazionario la sua fase si cancella in `|T|²`, ma le ampiezze direzionali modificano la fase e filtri diversi tra look possono lasciare termini differenziali.
- Il contributo nonlineare complesso `P_nlin(k,t)` si somma vettorialmente; OSW lo sottrae tramite LUT di vento, direzione e wave age prima dell'inversione.
- Patch finita, peak drift, finestre temporali da 6 s, overlap, corrente `k dot U`, shift residuo e decorrelazione sono ulteriori termini di bias.

Per ipotesi T=13.33 s, il solo matching della derivata a zero richiederebbe `B/A=0.146`. Sul baseline PVP reale 0-11.589 s quel modello produce però `-0.480 rad/s`, non -0.351. Una miscela bidirezionale quasi-lineare stazionaria non basta: servirebbe un termine netto aggiuntivo di circa `+0.120 rad/s`, la cui origine non è stata calibrata in questo blocco. Le LUT C-band Sentinel-1 non sono trasferibili numericamente all'Umbra X-band nearshore.

## Sensitivity analysis SAR-only

Sono state valutate 24 configurazioni valide senza dati esterni e senza riselezionare il massimo a ogni variante.

| Famiglia | slope min...max (rad/s) | periodo min...max (s) | max variazione relativa da -0.350972 |
|---|---:|---:|---:|
| look width 5.5/6.0/6.5 s, 9 centri comuni | -0.346270...-0.341911 | 18.145...18.377 | 2.58% |
| overlap subsampling 80/60/40% | -0.351929...-0.341030 | 17.854...18.424 | 2.83% |
| ROI baseline e cinque crop 80% | -0.366873...-0.350220 | 17.126...17.941 | 4.53% |
| patch radius 1-5 e quattro offset di un bin | -0.367782...-0.345942 | 17.084...18.163 | 4.79% |

Tutte le 24 varianti mantengono pendenza negativa, unwrapping giustificato e `R² >= 0.997`. L'intervallo complessivo è `-0.367782...-0.341030 rad/s` (`17.084...18.424 s`); la mediana coincide con il valore congelato. La pendenza è quindi una proprietà robusta del dato/processamento locale, non del singolo set di parametri, pur mostrando una sistematica ROI/patch fino a circa 5%.

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
