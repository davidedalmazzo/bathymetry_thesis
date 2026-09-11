# CHECKPOINT_7 — spatial-peak convergence, bathymetry and internal-dispersion gate

## Esito

**Classificazione finale: C.** Il massimo aggregato non migra verso 95–105 m: le mediane delle ROI grandi restano 126.0–130.9 m. Tuttavia il campo non è abbastanza omogeneo e il lobo non contiene abbastanza elementi radiali indipendenti per discriminare una curva `omega(k)` o stimare `d omega/dk` con incertezza difendibile.

Il risultato batimetrico della ROI storica è separatamente **B-like** (mediana circa 11.0 m NAVD88), ma non basta a classificare B: la ROI storica correttamente riproiettata interseca costa/void, mentre i rettangoli rigorosamente tutto-acqua hanno mediane 13.1–16.4 m e un forte gradiente cross-shore. Non è stata scelta una classe forzando l'accordo tra lunghezza d'onda e profondità.

`omega(k)` **non è sufficientemente risolta**. Di conseguenza i modelli con `b0` e `b0+b1(k-kp)` non sono stati fittati; non sono stati formati nuovi 11 sliding look sulla ROI grande. Lo zero-padding non è stato trattato come informazione indipendente.

## Guardrail software e valori congelati

- Ambiente usato: `D:\Dati Tesi\Umbra\.venv`, SarPy 2.0.1.
- Gate prima dell'analisi scientifica: suite completa precedente, **40 passed in 9.25 s**, inclusi i test SarPy-dependent.
- Verifica finale dopo l'aggiunta dei test Block 7: **42 passed in 2.62 s**; log JUnit in `PYTEST_FULL.xml`.
- `T_SAR = 17.902230457045317 s` e `slope = -0.3509722055168202 rad/s` sono rimasti congelati.
- Restano distinte `18.068061721 s` (processed aperture duration SICD) e `22.540812513 s` (dwell/slow-time CPHD disponibile).
- Nessun dwell sweep 5–16 s e nessuna inversione batimetrica definitiva.

## Correzione geodetica necessaria

La geolocalizzazione delle ROI dei blocchi precedenti era intenzionalmente una localizzazione/display a HAE costante dello SCP (`+101.5247567 m`). Questa quota non può essere usata per interrogare un DEM marino nearshore. L'API ufficiale NOAA GEOID18 restituisce al centro storico `N = -36.376 m`, errore modellistico 0.032 m; per `H_NAVD88 = 0`, la superficie di proiezione adottata è quindi `HAE = -36.376 m` ([NOAA NGS Geoid Height Service](https://geodesy.noaa.gov/web_services/geoid.shtml)).

La riproiezione del pixel SICD `(10000, 82800)` sposta il punto orizzontale di 341.92 m rispetto alla localizzazione SCP-HAE, a UTM 10N `(716210.610, 3827777.094) m`. Tutte le statistiche batimetriche definitive di questo checkpoint usano la proiezione sea-surface; i valori provvisori ottenuti a `+101.525 m` sono stati scartati.

## A. Supporto e convergenza del picco

Il massimo rettangolo ruotato, interamente sotto `-2 m NAVD88` sul campionamento di controllo e contenuto nel SICD, è `1440 x 650 m`. È orientato con l'asse lungo al bearing congelato del vettore d'onda, 79.8357°. Il supporto comprende circa 11 lunghezze d'onda a 130.9 m. Le ROI testate hanno `L_parallel = 540, 720, 900, 1080, 1260, 1440 m` e `L_perp = 650 m`.

Sono state analizzate due sequenze:

1. rettangoli concentrici nel supporto massimo;
2. rettangoli ancorati al bordo nearshore, che aggiungono progressivamente supporto offshore senza allontanare il bordo storico.

Per ogni ROI e ciascuno dei tre look nominali sono state usate tre opzioni: mean+Hann, plane+Tukey 0.10, quadratic+Tukey 0.25. Lo zero-padding 2x interpola il massimo; la risoluzione nativa resta `Delta f_parallel = 1/L_parallel` e `Delta k_parallel = 2 pi/L_parallel`.

| L_parallel (m) | lambda mediana nearshore-anchored (m) | P10–P90 look/window (m) | theta mediana (° mod 180) | Delta f nativa (cy/m) |
|---:|---:|---:|---:|---:|
| 540 | 153.21 | 134.28–153.21 | 73.07 | 0.001852 |
| 720 | 130.91 | 130.25–143.12 | 74.09 | 0.001389 |
| 900 | 128.57 | 128.45–137.68 | 79.84 | 0.001111 |
| 1080 | 127.06 | 126.94–168.92 | 79.84 | 0.000926 |
| 1260 | 126.00 | 125.88–170.40 | 79.84 | 0.000794 |
| 1440 | 130.91 | 125.10–171.19 | 79.84 | 0.000694 |

Le ultime tre mediane variano del 3.84%, quindi il valore centrale è vicino a 130 m e non a 100 m. Però al massimo supporto la dispersione P10–P90 tra look/window è 35.2%: alcuni stimatori selezionano il lobo lungo 169–178 m. La conclusione corretta è quindi: **tendenza centrale vicino a 130 m, ma nessuna convergenza robusta del singolo picco**.

## B. Omogeneità e broadening

Le sotto-ROI indipendenti danno:

- cross-shore/asse `k`: lambda = 158.80, 134.19, 158.80 m; CV = 9.44%; bearing = 86.85°, 91.75°, 72.82°;
- alongshore/perpendicolare a `k`: lambda = 180.0, 180.0, 130.91 m; CV = 17.32%. I due valori a 180 m sono sul limite lungo della banda di ricerca e indicano assenza di un massimo interno stabile, non misure precise di 180 m.

Nel rettangolo 1440 m il FWHM radiale mediano è `0.001399 cy/m`, mentre il bin nativo è `0.0006944 cy/m`: il lobo occupa soltanto 2.014 elementi radiali nativi. Non si può separare in modo affidabile broadening fisico, leakage della finestra e miscela spaziale di componenti.

## C. Residui della serie congelata

Il fit congelato non è stato modificato. I residui diretti hanno RMSE 0.05323 rad e massimo assoluto 0.09236 rad. L'autocorrelazione biased ai primi lag è `rho(1)=0.499`, `rho(2)=-0.366`, `rho(3)=-0.746`.

Una ricerca sinusoidale esclusivamente diagnostica trova periodo 7.184 s, ampiezza 0.0675 rad e `R2_residual = 0.844` (`Delta AIC = -14.41` rispetto alla costante). Il risultato non è usato per correggere la pendenza: ci sono soltanto 11 look fortemente sovrapposti, la frequenza è stata cercata e il record contiene meno di due cicli indipendenti robusti.

## D. Batimetria indipendente

Il mosaico ufficiale CUDEM 1/9 arc-second della California comincia circa a 36.75°N e non copre Point Arguello ([indice tile NOAA CUDEM](https://coast.noaa.gov/htdata/raster2/elevation/NCEI_ninth_Topobathy_2014_8483/CA/index.html)). Non è stato quindi attribuito impropriamente il nome CUDEM a un altro prodotto.

È stato usato il prodotto NOAA/OCM effettivamente coprente la ROI: **2009–2011 CA Coastal California TopoBathy Merged Project DEM, Smoothed with Voids**, catalogo InPort 49417 ([metadata ufficiali NOAA](https://www.fisheries.noaa.gov/inport/item/49417)). Sono stati scaricati soltanto nove tile da 1500 x 1500 celle attorno alla ROI, sotto `Vandenberg/bathymetry`.

- risoluzione orizzontale nominale: 1 m;
- riferimento orizzontale del tile: NAD83 / UTM zona 10N, EPSG:26910; il WKT del prodotto include l'etichetta NAD83(NSRS2007);
- riferimento verticale: quota NAVD88 in metri, EPSG:5703;
- tidal datum del raster consegnato: nessuno. Sorgenti originariamente su datum diversi, incluso MLLW dove applicabile, sono state trasformate a NAVD88 con VDatum durante il merge;
- pubblicazione: marzo 2014; conversione COG NOAA: 23 luglio 2024;
- età sorgenti: lidar topografico 2009–2011, lidar batimetrico principalmente 2009–2010; sorgenti acustiche di età variabile. Il GeoTIFF non conserva la data per singola cella.

Le profondità sono riportate come `-elevation_NAVD88`, positive verso il basso; **non sono chart depths MLLW** e non è stata applicata alcuna correzione di marea.

| Supporto | P5 | P25 | mediana | P75 | P95 | gradiente parallelo a k |
|---|---:|---:|---:|---:|---:|---:|
| ROI storica 540 x 540 m, non tutta-acqua dopo correzione HAE | 5.00 | 7.19 | 11.00 | 12.15 | 13.01 | -16.41 m/km |
| tutto-acqua nearshore-anchored 540 x 650 m | 11.22 | 12.13 | 13.09 | 14.00 | 14.89 | circa -9 m/km |
| massimo tutto-acqua 1440 x 650 m | 11.76 | 13.69 | 16.44 | 20.08 | 23.03 | -8.79 m/km |

Il gradiente perpendicolare a `k` nel supporto massimo è +1.51 m/km. Il forte gradiente parallelo conferma che la ROI grande miscela profondità e potenzialmente stati d'onda diversi.

## E. Gate del test interno di dispersione

Il gate richiedeva almeno quattro elementi radiali nativi nel lobo, dispersione look/window <=15% e CV delle sotto-ROI <=10%. Risultati:

| criterio | valore | esito |
|---|---:|:---:|
| almeno 10 lambda lungo k | 11.0 | pass |
| elementi radiali indipendenti nel lobo | 2.014 (soglia 4) | fail |
| escursione ultime tre mediane | 3.84% (soglia 5%) | pass |
| P10–P90 look/window, ROI massima | 35.2% (soglia 15%) | fail |
| CV cross-shore | 9.44% (soglia 10%) | pass |
| CV alongshore | 17.32% (soglia 10%) | fail |

Per sola scala diagnostica, a `lambda=130.91 m` e profondità mediana 16.44 m la dispersione lineare dà `omega=0.5565 rad/s`, `T=11.291 s`, group velocity `9.741 m/s`; un bin radiale nativo corrisponde a circa `Delta omega=0.0425 rad/s`. Con soltanto due elementi indipendenti non ci sono gradi di libertà adeguati per distinguere `b0` da `b1`, né per un bootstrap realistico su `d omega/dk`. Fittare i molti campioni zero-padded/overlapping avrebbe prodotto pseudo-replicazione.

## F. Decision gate

**C — campo troppo eterogeneo / lobo troppo poco risolto per discriminare.**

- La mediana spaziale favorisce circa 130 m e non 95–105 m.
- La profondità storica corretta è circa 11 m, ma quella dei supporti rettangolari tutto-acqua cresce da 13 a 16 m e non è uniforme.
- La sensibilità a look/window e la suddivisione alongshore impediscono di associare in modo univoco il lobo aggregato a una singola componente dispersiva.
- `omega(k)` non è sufficientemente risolta per testare una curva di dispersione.

Il dwell sweep e l'inversione batimetrica restano esplicitamente fuori da questo checkpoint.

## Artefatti principali

- `BLOCK7_ROI_SUPPORT_PLAN.json`, `BLOCK7_ROI_SUPPORT_BATHYMETRY.png`
- `BLOCK7_SPATIAL_CONVERGENCE.csv`, `BLOCK7_SPATIAL_CONVERGENCE.json`, `BLOCK7_SPATIAL_CONVERGENCE.png`
- `BLOCK7_HOMOGENEITY.csv`
- `BLOCK7_BATHYMETRY_STATS.json`, `BLOCK7_BATHYMETRY_ROI.png`
- `BLOCK7_FROZEN_RESIDUAL_DIAGNOSTIC.json`, `BLOCK7_FROZEN_RESIDUAL_DIAGNOSTIC.png`
- `BLOCK7_INTERNAL_DISPERSION_GATE.json`
- `PYTEST_FULL.xml`
