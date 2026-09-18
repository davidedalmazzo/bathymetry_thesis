# Block15F — geometria BP12 e sensibilità della fase di trasferimento

## Risposta breve

Nel modello lineare verificato e limitato, la geometria BP12 induce una fase di trasferimento variabile e osservabile: `s_transfer=+0.00532…+0.00623 rad/s` sugli scenari dichiarati. È circa 1.3–1.6% della pendenza BP12 M0 al picco (`+0.40608 rad/s`) e supera numericamente la differenza M1−M0 (`−0.001707 rad/s`), ma è molto inferiore a uno scarto di ordine 0.12 rad/s. Non dimostra la causa della discrepanza: il risultato dipende da profondità/frequenza assunte e il termine idrodinamico/MTF X-band resta non identificato.

## Cosa è direttamente sostenuto da metadati e PVP

BP12 usa 32 look strettamente disgiunti formati in backprojection CPHD. Il signal array CPHD non è stato letto: si sono letti soltanto header/metadata già disponibili e PVP `TxTime`, `TxPos`, `RcvPos`, `SRPPos`, `SC0`, `SCSS`. Ogni look ha 4280–5274 impulsi; supporto nominale 0.7043999 s, span PVP interno effettivo 0.70412–0.70439 s. Il suo tempo rappresentativo è la media aritmetica esatta dei TxTime dei suoi impulsi, non il centro di Doppler o una stima di fase dell'onda. I tempi vanno da 0.355347 a 22.191504 s.

Il bersaglio fisso è il centro della griglia BP12: UTM 10N (715510.610, 3827627.094), superficie HAE **−36.376 m**, 288×130 a 5 m, asse 0 bearing UTM 79.8357237°. La HAE è quella di focalizzazione storica (zero NAVD88 approssimato tramite GEOID18), non SCP, fondale o livello marino istantaneo. Il picco non è riselezionato: `(133,65)`, `kx=−0.0479965544 rad/m`, `ky=0`, `|k|=0.0479965544 rad/m`, lambda=130.909 m, convenzione FFT dell'intensità BP12 congelata.

| Grandezza (media look) | primo | ultimo | min–max apertura |
|---|---:|---:|---:|
| Slant range [km] | 614.530 | 618.740 | 611.217–618.740 |
| Velocità [m/s] | 7657.601 | 7657.606 | 7657.595–7657.607 |
| R/V [s] | 80.251 | 80.797 | 79.817–80.797 |
| Incidenza [deg] | 22.814 | 23.885 | 22.013–23.885 |
| Azimuth view orizzontale [deg] | 85.183 | 125.090 | 85.183–125.090 |
| Azimuth volo [deg] | 191.113 | 191.261 | 191.113–191.261 |
| Angolo view−flight firmato [deg] | 105.930 | 66.171 | 66.171–105.930 |
| Squint rispetto a broadside [deg] | +15.930 | −23.829 | −23.829–+15.930 |
| k·LOS orizzontale [rad/m] | −0.047878 | −0.034571 | −0.047878…−0.034571 |
| k·direzione volo [rad/m] | +0.016372 | +0.016488 | +0.016372…+0.016488 |

Il bearing view è quello **dal punto di griglia verso il sensore**, ottenuto in ENU locale; non è la direzione di volo né l'asse 0 BP12. Squint è definito qui come `(view−flight)−90°`, con segno dall'angolo orientato locale; non è un campo vendor. Le ampiezze nelle tabelle sono media/min/max sulle PVP assegnate al singolo look. Per esempio, nel primo look incidenza varia internamente 22.7508–22.8795° e squint 105.308–106.550°: la geometria al centro/alla media è quindi una buona ma non esatta riduzione; tutte le variazioni sono disponibili nel CSV.

## Modello auditato e convenzione

Il dettaglio, formule, unità, fonti locali e limiti è in `BLOCK15F_MODEL_ASSUMPTIONS.md`. Si è valutato esclusivamente `H=T_t+T_vb`, con tilt/RAR geometrico linearizzato e termine di densità/Jacobiano di velocity bunching. La velocità orbitale è coerente in profondità finita: orizzontale `a omega coth(kh)`, verticale `a omega`. `T_h=0`: non esiste nel progetto una formula idrodinamica/relaxation X-band verificabile con parametri locali. Le tavole OSW C-band non sono state trasferite né calibrate.

Il termine `T_vb` è solo Jacobiano lineare della mappa `y'=y+(R/V)u_LOS`; non è sommato a un secondo shift/displacement MTF. La formula broadside non è dichiarata esatta per spotlight: `k_f` è proiettato sulla traiettoria PVP effettiva; view, flight e assi BP12 non sono imposti ortogonali. Il modello lineare non descrive fold/caustiche o scattering Bragg; `|H|` non è interpretato come altezza d'onda.

Con `z_j=A H_j exp(i s_wave t_j)` e `F_secondaria*conj(F_riferimento)`, vale `arg(z_j conj(z_r))=s_wave delta_t+arg(H_j conj(H_r))`. Se H è costante, cancella esattamente. Il test numerico verifica segno, swap riferimento/secondario e lobo coniugato: i due ultimi invertono la pendenza. Non sono introdotte fasi libere look-per-look.

## Sensibilità prefissata

| Scenario | Assunzioni non misurate | s_transfer [rad/s] | Curvatura fase H RMS [rad] | min–max |H| [m^-1] | min cancellation ratio |
|---|---|---:|---:|---:|---:|
| T13_depth5 | T=13.33 s, h=5 m | +0.005598 | 0.001836 | 0.991–1.202 | 0.9942 |
| T13_depth10 | T=13.33 s, h=10 m | +0.006215 | 0.001192 | 0.724–0.812 | 0.9832 |
| T13_depth20 | T=13.33 s, h=20 m | +0.005323 | 0.000502 | 0.637–0.676 | 0.9718 |
| T17.902_depth10 | T=17.902230457 s, h=10 m | +0.006234 | 0.001226 | 0.544–0.612 | 0.9780 |

`cancellation ratio=|H|/(|T_t|+|T_vb|)`. Tutti gli scenari restano lontani da cancellazione; grandi rotazioni di fase da `H≈0` non sono il meccanismo qui. Il modello prevede fase quasi lineare ma non perfettamente: curvatura 0.0005–0.0018 rad. Nel sintetico di singolo coefficiente con `s_wave=+0.4`, il trasferimento costante recupera +0.4 esattamente, quello variabile recupera `+0.40532…+0.40623`, cioè `s_wave+s_transfer`, confermando algebra e segno senza costruire una patch MSC artificiale.

T=13.33 è solo ipotesi di associazione alla stessa componente; non entra nella selezione. T=17.902230457 è il valore SAR-only congelato, non un periodo fisico imposto. Nessuna pendenza trasferimento viene sottratta da un fit reale. Non si confonde il precedente T_SAR congelato con il periodo BP12 circa 15.25 s inferito in altri blocchi.

## Conclusione e discriminazione futura

La variazione geometrica dei look è reale e ampia (view ~39.9°, incidenza ~1.87°, `k·LOS` ~0.01331 rad/m), e nei modelli verificati induce una fase osservabile ma piccola: circa +0.006 rad/s. Può essere una covariata processistica più rilevante della differenza M0–M1, ma non spiega da sola un bias di ~0.120 rad/s. L'esito è condizionato, non identificativo: un MTF idrodinamico, componente vicina, offset additivo e rumore correlato possono ancora produrre traiettorie complesse simili.

Un osservabile discriminante sarebbe una dipendenza ripetibile della fase residua dal predittore geometrico PVP (in particolare `k·LOS`/squint) su bin fissati e sui loro coniugati, verificata contro un controllo terrestre e contro ampiezza/coerenza. Non è stato eseguito qui perché richiede un disegno separato per non riaprire la selezione o introdurre fasi libere.

Un solo prossimo esperimento consigliato: **simulazione sintetica prefissata di separabilità fra due componenti vicine, con la geometria PVP qui auditata come modulazione comune**, confrontando pattern di fase, ampiezza e coniugazione senza correggere dati reali. È più mirata del fit di ulteriori termini fisici non identificati.

## Verifica

Quattro nuovi test mirati verificano proiezioni/unità, limite acqua profonda, cancellazione H costante, deriva imposta con segno, swap/coniugazione e trasferimento quasi nullo. Gli hash degli artefatti Block15D/E, manifest BP12, metadata CPHD e sorgenti Block10 elencati in configurazione sono guardati. Una sostituzione compatibile NumPy `speed.ptp→np.ptp(speed)` è stata fatta dopo il freeze di configurazione, prima dell'audit PVP; non cambia formule, scenari o risultati e il manifest finale registra gli hash sorgente effettivi.

Nessun signal CPHD, download, dwell sweep, nuova retroproiezione, stack, inversione, commit o push. **STOP — Block15F completato.**
