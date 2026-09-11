# CHECKPOINT_6 — mappa della pendenza di fase nearshore e teoria cross-spectrum

## Esito sintetico

Il Blocco 6 è completato senza dwell sweep, senza inversione batimetrica e senza modificare il confronto NDBC. Il valore SAR-only resta congelato a

\[
T_{\rm SAR}=17.902230457045317\ {\rm s},\qquad
s_0=-0.3509722055168202\ {\rm rad\,s^{-1}}.
\]

La mappa conserva 68 patch coerenti nell’intervallo 40–500 m. Il lobo di alta qualità connesso al bin congelato contiene 22 patch; il lobo coniugato ne contiene altre 22. Il bin originale è riprodotto senza differenza numerica, con \(R^2=0.998288\), errore selezionato OLS/HAC-4 di 0.004844 rad/s, coerenza adiacente minima 0.972647 e coerenza minima fra gli anchor indipendenti 1–6–11 pari a 0.559481.

Conclusione sperimentale: **il valore circa +0.120 rad/s non è una correzione costante sul piano spettrale e non emerge una dipendenza sistematica robusta dall’orientamento dopo aver controllato \(|k|\)**. Nel solo anello vicino al picco compare un indizio di pendenza più negativa al crescere di \(|k_{\rm az}|\), ma sono appena sette patch sovrapposte e non costituiscono campioni indipendenti.

Conclusione teorica: **nel limite quasi-lineare, stazionario e unidirezionale la fase deve evolvere esattamente con \(-\omega\)** per la convenzione usata. Una differenza \(d\phi_{\rm SAR}/dt\ne-\omega\) può invece essere prodotta dalla miscela \(S(-\mathbf{k})/S(\mathbf{k})\), dal contributo non lineare \(P_{\rm nlin}\), o da una fase del trasferimento che varia realmente con il centro Doppler/look. La fase statica della MTF non basta, perché nell’equazione OSW quasi-lineare compare \(|T|^2\).

## Vincoli congelati

| Quantità | Valore / stato |
|---|---:|
| \(T_{\rm SAR}\) congelato | 17.902230457045317 s |
| Pendenza SAR congelata | −0.3509722055168202 rad/s |
| \(\lambda_{\rm SAR}\) congelata | 130.6028192373831 m |
| Direzione congelata | 79.83572372864876° modulo 180° |
| Convenzione cross-spectrum | `F_secondary * conj(F_reference)` |
| Confronto NDBC | invariato; nessuna nuova selezione o ottimizzazione |
| Processed aperture SICD | 18.068061721230308 s |
| Dwell/slow-time CPHD disponibile | 22.540812513364376 s |

Le ultime due durate restano quantità distinte. Tutti gli 11 centri temporali sono quelli fisici derivati dal mapping Doppler–PVP del Blocco 4.

## Assi locali e contenuto della mappa

Per evitare ambiguità, in questo blocco:

- \(k_x\) è la proiezione del vettore d’onda EN sulla direzione positiva della Grid Row/range locale, bearing 281.178627°; la stessa retta non orientata è 101.178627°.
- \(k_y\) è la proiezione sulla direzione positiva della Grid Col/azimuth locale, bearing 191.457983°; la retta non orientata è 11.457983°.
- La separazione fra gli assi locali è 89.720644°.
- Il vettore congelato forma 21.342904° con l’asse range locale.

Per ciascuna riga del CSV sono registrati: indici e offset FFT, \(k_E,k_N,k_x,k_y\) in cicli/m e rad/m, \(|k|\), lunghezza d’onda, bearing, angoli rispetto a range e azimuth, pendenza, errori OLS e HAC-4, RMSE, \(R^2\), coerenze adiacenti e indipendenti, potenza locale, branch coniugato e bias diagnostici.

## Stima locale e criteri di accettazione

È stata mantenuta la patch gaussiana 5×5, \(\sigma=1\) bin, del Blocco 4. Per ogni punto e look \(j\):

\[
C_j(\mathbf{k})=\sum_{\mathbf{q}\in\mathcal P}w(\mathbf{q})
F_j(\mathbf{k}+\mathbf{q})F_1^*(\mathbf{k}+\mathbf{q}).
\]

La fase è stata srotolata solo quando tutte le seguenti condizioni erano verificate:

- coerenza minima fra look adiacenti almeno 0.70;
- coerenza minima per ciascuna coppia indipendente 1–6, 6–11 e 1–11 almeno 0.25;
- passo temporale diretto e fase adiacente minori di \(\pi/2\);
- discrepanza fra passo diretto e cross-phase adiacente non superiore a 0.25 rad.

La mappa tabellata usa il precedente intervallo fisico 40–500 m. L’errore della pendenza è il massimo fra errore OLS ed errore Newey–West con lag 4, coerente con la correlazione introdotta dagli sliding looks.

## Controlli numerici

La simmetria hermitiana delle FFT di intensity fornisce un controllo interno molto forte:

\[
s(-\mathbf{k})=-s(\mathbf{k}).
\]

Al bin congelato la somma fra pendenza e pendenza coniugata è −1.11×10⁻¹⁶ rad/s; l’errore massimo sull’intera mappa valida è 1.67×10⁻¹⁶ rad/s. Questo conferma numericamente sia l’ordinamento del branch sia il segno della convenzione cross-spectrum.

I conteggi sono:

| Selezione | Patch |
|---|---:|
| Coerenza e unwrap validi, tutti i \(k\) | 73 |
| Mappa 40–500 m | 68 |
| Alta qualità: \(R^2\ge0.95\), errore ≤0.04 rad/s, potenza ≥5% del picco | 48 |
| Lobo connesso al bin congelato | 22 |
| Lobo coniugato | 22 |

## Dipendenza dall’orientamento

Nel lobo connesso al picco:

- \(\lambda\) varia da 80.54 a 191.51 m;
- l’angolo rispetto al range varia da 0.28° a 56.03°;
- la pendenza allineata varia da −0.42286 a −0.34594 rad/s;
- il bias rispetto alla curva di dispersione diagnostica associata a 13.33 s e 10.627 m varia da −0.02384 a +0.31454 rad/s.

Il valore di mappa al bin intero congelato è +0.119752 rad/s; il confronto analitico esatto che usa \(\lambda=130.602819\) m e \(T=13.33\) s è +0.1203845 rad/s. La piccola differenza deriva dal centro del bin intero, \(\lambda=130.79\) m, e non da un retuning.

Le correlazioni descrittive sul lobo sono:

| Relazione | Spearman \(\rho\) | n |
|---|---:|---:|
| bias vs \(|k|\) | +0.983 | 22 |
| bias vs \(|k_{\rm az}|\) | +0.269 | 22 |
| bias vs angolo dal range | +0.014 | 22 |

Nel modello standardizzato `bias ~ |k| + |k_az|`, un incremento di una deviazione standard di \(|k|\) vale +0.09441 rad/s, mentre quello di \(|k_{\rm az}|\) vale −0.000265 rad/s con errore descrittivo 0.003057 rad/s. Sostituendo \(|k_{\rm az}|\) con l’angolo, l’effetto angolare è −0.00124 ± 0.00279 rad/s per deviazione standard.

Nell’anello \(0.85|k_0|\le|k|\le1.15|k_0|\), n=7, si trova \(\rho=-0.714\) fra pendenza e \(|k_{\rm az}|\). È un indizio coerente con un termine di velocity bunching dipendente da \(k_y\), ma non supera il problema di numerosità effettiva e sovrapposizione delle patch.

L’andamento dominante del bias con \(|k|\) non va letto come dispersione misurata punto per punto: una parte del lobo è leakage/risposta spettrale dello stesso sistema ondoso, e la pendenza osservata rimane molto più piatta della curva \(\omega(|k|)\). Non viene quindi stimata alcuna legge correttiva da questi 22 bin.

## Derivazione quasi-lineare minima

La formulazione Engen–Johnsen è la base del cross-spectrum fra look; l’ATBD Sentinel-1 OSW scrive il contributo quasi-lineare come

\[
P_{\rm qlin}(\mathbf{k},t)=C(\mathbf{k})\left[
A(\mathbf{k})e^{-i\omega t}+B(\mathbf{k})e^{+i\omega t}\right],
\]

con

\[
C={U(\mathbf{k})\over2}\exp\!\left[-\left({k_y\lambda_c\over2\pi}\right)^2\right],\quad
A=|T(\mathbf{k})|^2S(\mathbf{k}),\quad
B=|T(-\mathbf{k})|^2S(-\mathbf{k}).
\]

Per \(C\) stazionario:

\[
{d\arg P_{\rm qlin}\over dt}=
\omega{B^2-A^2\over A^2+B^2+2AB\cos(2\omega t)}.
\]

Quindi:

- se \(B=0\), \(d\phi/dt=-\omega\) esattamente;
- se \(B/A\ne0\), la pendenza è variabile e non coincide in generale con \(-\omega\);
- una fase statica di \(C\) o di \(T\) modifica \(\phi_0\), non la pendenza;
- l’orientamento può però cambiare \(A/B\), perché \(T\), cutoff azimutale e velocity bunching dipendono da \(k_y\).

Il modello generale più semplice è

\[
P=C(t)\left[Ae^{-i\omega t}+Be^{+i\omega t}\right]+N(t),
\qquad
{d\phi\over dt}={\operatorname{Im}\{P^*\dot P\}\over|P|^2},
\]

dove \(N=P_{\rm nlin}\). Per una sola componente e un termine non lineare stazionario:

\[
{d\phi\over dt}=-\omega
{A^2+A\operatorname{Re}[N^*e^{-i\omega t}]\over
A^2+|N|^2+2A\operatorname{Re}[N^*e^{-i\omega t}]}.
\]

Questo è il termine più diretto capace di produrre una pendenza diversa anche quando \(S(-\mathbf{k})=0\). L’ATBD OSW sottrae esplicitamente \(P_{\rm nlin}\) prima dell’inversione quasi-lineare; qui quella lookup table non è disponibile. Le equazioni usate sono le 34–37 dell’[ATBD Sentinel-1 OSW](https://sentinels.copernicus.eu/documents/247904/349449/S-1_L2_OSW_Detailed_Algorithm_Definition.pdf); la formulazione originaria è [Engen & Johnsen, 1995](https://doi.org/10.1109/36.406690).

## Ordine di grandezza con la geometria Umbra

L’ATBD usa

\[
T(\mathbf{k})=ik_yT_\xi(\mathbf{k})+T_\sigma(\mathbf{k}),\qquad
T_\xi\sim{R\over V}\omega
\left[{k_x\over|k|}\sin\theta+i\cos\theta\right].
\]

Per Umbra:

| Quantità | Valore |
|---|---:|
| Slant range \(R\) | 610403.751 m |
| Velocità piattaforma \(V\) | 7657.751 m/s |
| \(R/V\) | 79.7106 s |
| Incidenza | 21.8429° |
| \(|k_{\rm az}|\) al picco | 0.0175093 rad/m |
| Core geometrico \(|T_\xi|\), per metro d’ampiezza | 37.226 m/m |
| \(|k_{\rm az}T_\xi|\), per metro d’ampiezza | 0.6518 m⁻¹ |

Come solo scala non fittata, mantenendo congelato l’Hm0 della partizione NDBC già usata nel Blocco 5 (1.637 m), l’ampiezza sinusoidale equivalente è 0.579 m. Ne seguono:

- parametro del core ATBD \(a|k_yT_\xi|\approx0.377\), assumendo unitario il tuning/switch Umbra non disponibile;
- parametro di bunching da velocità orbitale a profondità diagnostica 10.627 m circa 0.451.

Sono valori abbastanza grandi da rendere plausibili termini non lineari dell’ordine delle decine di percento. Non predicono tuttavia +0.120 rad/s: per farlo servirebbero la lookup completa \(P_{\rm nlin}\), la MTF RAR X-band con vento, il fattore di tuning e il trasferimento specifico di ogni look.

Rispetto a \(T=13.33\) s, la differenza analitica richiesta è 0.1203845 rad/s, il 25.54% di \(\omega\). Nel modello `onda + N stazionario`, il minimo favorevole richiede \(|N|/A\approx0.343\) se in fase e 0.586 in quadratura. Una spiegazione come semplice advezione uniforme richiederebbe invece \(U_\parallel\approx2.50\) m/s; è un ordine di grandezza elevato e non viene adottato come spiegazione preferita.

La risposta corretta alla domanda “può arrivare a 0.120 rad/s?” è quindi: **l’ordine di grandezza della non linearità SAR è compatibile con un bias importante, ma i dati e i coefficienti disponibili non consentono di calcolare né attribuire univocamente 0.120 rad/s**.

## Limiti e guardrail

- Le patch 5×5 vicine si sovrappongono: gli errori delle regressioni fra bin sono descrittivi e anti-conservativi.
- Il lobo spettrale contiene leakage dello stesso picco; i bin non sono componenti oceaniche indipendenti.
- Le profondità 10.627 m e 5.556 m sono i valori diagnostici congelati del Blocco 5, non batimetria stimata.
- Non sono disponibili per Umbra la lookup \(P_{\rm nlin}\), la MTF RAR oceanografica X-band e il tuning OSW.
- Il controllo di terra precedente esclude un grande phase ramp comune, ma non una MTF oceanica dipendente da velocità orbitale.
- Non è stato eseguito alcun dwell sweep.

## Artefatti

- `BLOCK6_NEARSHORE_PHASE_SLOPE_MAP.csv`: tabella completa delle 68 patch.
- `BLOCK6_NEARSHORE_PHASE_SLOPE_MAP.npz`: matrici, fasi, maschere e assi fisici.
- `BLOCK6_PHASE_SLOPE_SUMMARY.json`: risultati, soglie, regressioni e guardrail.
- `BLOCK6_CROSS_SPECTRUM_THEORY.json`: derivazione e scaling geometrico.
- `BLOCK6_NEARSHORE_PHASE_SLOPE_MAP.png`: potenza, pendenza, \(R^2\) e bias.
- `BLOCK6_ORIENTATION_DIAGNOSTIC.png`: dipendenza da \(|k|\), orientamento e anello vicino al picco.
- `tests/TEST_REPORT_BLOCK6.md`: test numerici e limite ambientale documentato.

## Stato

**CHECKPOINT_6 raggiunto.** Il risultato congelato non è stato modificato; il Blocco 6 non giustifica una correzione costante o una nuova stima del periodo. Il passo scientifico successivo, se autorizzato, dovrebbe separare esplicitamente leakage, branch opposto e contributo non lineare con un dataset più favorevole o con un forward model ocean-to-SAR calibrato.

## Criteri separati per una nuova ricerca nel catalogo Umbra

Un dataset di validazione ideale dovrebbe soddisfare, in ordine di priorità:

1. **Dwell e dati complessi:** CPHD/PVP disponibile e SICD complesso della stessa acquisizione; dwell CPHD preferibilmente almeno 30 s e processed aperture almeno 24–25 s, sufficienti per almeno tre look indipendenti da 6–8 s e 15 o più sliding centers.
2. **Swell dominante e stretto:** una sola partizione principale, \(T_p\) circa 12–20 s, Hm0 della partizione almeno 1.5 m, banda spettrale circa ≤0.015–0.020 Hz e directional spread preferibilmente ≤15°. Il vento mare concorrente dovrebbe essere debole.
3. **Direzione quasi-range:** vettore di propagazione entro 5° dal range locale, accettabile fino a 10°, verificato sulla proiezione locale della Grid SICD e non sull’AzimAng CPHD a un tempo diverso.
4. **Ground truth spettrale:** boa direzionale o array entro circa 25 km e ±15 min, con density e coefficienti direzionali completi, non solo DPD/APD/MWD; preferibile una sorgente con frequenza almeno 30 minuti.
5. **Scena pulita:** ROI oceanica almeno 1–2 km per lato, senza costa, navi, wake o fronti forti, più una ROI terrestre stabile nello stesso prodotto.
6. **Geometria e metadata:** incidenza e polarizzazione documentate, supporto Doppler completo, PVP continuo e mapping Doppler–slow-time monotono; evitare prodotti con trimming o processing non ricostruibile.
7. **Contesto ausiliario:** vento, corrente superficiale e batimetria ad alta risoluzione disponibili come controlli indipendenti, senza usarli per scegliere il ramo di fase.
8. **Ridondanza:** idealmente almeno due acquisizioni dello stesso swell con geometrie diverse, una quasi-range e una con \(k_{\rm az}\) significativo, per isolare sperimentalmente il termine dipendente dall’orientamento.

