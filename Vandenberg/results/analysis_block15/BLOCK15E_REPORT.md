# Block 15E — robustezza di M1 a rumore correlato e partizione temporale

Completato il 2026-09-12. Questo blocco chiude la verifica corrente dell'offset statico. Non sottrae offset, non corregge frequenze e non identifica l'origine fisica di un termine additivo.

## Risultato congelato da verificare

Sul picco BP12 fissato (133,65), il Block15D dava `s_M0=+0.40607604` e `s_M1=+0.40436881 rad/s`: differenza M1−M0 `−0.00170723 rad/s`, valore assoluto pari allo 0.4204% di M0. Il rapporto `|c|/|a|` di M1 era 0.304740. Nei quattro training da 24 look, `s_M1` variava fra 0.398586 e 0.416544 rad/s (span 0.017957); CV del rapporto 0.0982 e dispersione complessa normalizzata di c 0.0773.

| Holdout Block15D | Tipo | NMSE M0 | NMSE M1 | Guadagno M1 |
|---|---|---:|---:|---:|
| 0–7 | estremo | 0.605645 | 0.409022 | 32.47% |
| 8–15 | interno | 0.151715 | 0.117403 | 22.62% |
| 16–23 | interno | 0.148874 | 0.084298 | 43.38% |
| 24–31 | estremo | 0.352575 | 0.190956 | 45.84% |

Il guadagno aggregato era 35.88%. Questa prestazione predittiva e la piccola variazione di pendenza sono risultati distinti; la seconda non è una correzione.

## Disegno prefissato

`BLOCK15E_CONFIG.json` è stato scritto prima dei nuovi fit reali e sintetici. Restano invariati BP12, intensità lineare e preprocessing Block15D, tempi effettivi, picco, 15 bin, M0/M1, ricerca signed ±3.21445109 rad/s, costo, profili, alternative e criteri di stabilità. I coefficienti reali provengono dal risultato Block15D: nessuna nuova lettura radar.

Il nullo è una sola componente con i parametri M0 stimati al picco più rumore gaussiano complesso proprio e circolare:

`E[epsilon_i conj(epsilon_j)] = sigma² exp(-|t_i-t_j|/tau)`.

Parte reale e immaginaria hanno varianza `sigma²/2`, covarianza incrociata zero; condizione iniziale stazionaria `CN(0,sigma²)`. La ricorrenza usa `rho_i=exp(-(t_i-t_(i-1))/tau)`, quindi rispetta i tempi non perfettamente uniformi. `tau=0` è indipendente; scenari prefissati `tau=0.5, 2, 5 s`. Questi sono scenari, non stime del processo reale.

Scelta primaria: `sigma=489.7732`, RMS non centrato dei residui M0 completi; 300 repliche per tau. È deliberatamente conservativa ma può inglobare proprio il contributo che M1 descrive. Sensibilità: `sigma=301.5953`, RMS dei residui M1; 100 repliche per tau, potenzialmente sottostimata perché ottenuta dal modello più flessibile. Seed `SeedSequence([150500, regime, replica])`; le scale condividono innovazioni standard, e ogni serie è identica nei due confronti di partizione. Totale 1600 serie, nessun fallimento o esclusione.

Per ogni serie sono stati rifatti entrambi i modelli e tutti i fit di validazione. La partizione primaria è quella 4×8 del 15D. L'unica alternativa ha otto test consecutivi da quattro look; i due look immediatamente prima e dopo sono esclusi dal training. Restano 24 campioni per i sei blocchi interni e 26 agli estremi, con span del training 21.84 s internamente e 17.61 s agli estremi. Distanza minima training–test circa 2.10–2.11 s. Non garantisce indipendenza per tau lungo.

Per la descrizione alternativa è stato prefissato lo stesso guadagno aggregato minimo del 10%, stabilità invariata, almeno 6/8 fold migliorati e miglioramento a entrambi gli estremi. I risultati continui sono riportati comunque; gli otto fold non sono repliche indipendenti.

## Residui reali e incertezza del rumore

M0 ha RMS 489.77 e residuo medio `−208.82+313.27i`; dopo centratura RMS 313.26. M1 ha media numericamente nulla per costruzione e RMS 301.60. L'ACF centrata reale al primo lag (~0.704 s) è 0.649 per M0 e 0.594 per M1; a ~1.409 s è 0.460 e 0.366. Le parti immaginarie dell'ACF arrivano a circa 0.33/0.26. Un OU circolare con covarianza reale non rappresenta questa rotazione complessa: è un nullo parsimonioso, non un fit completo dei residui.

Gli RMS per quattro segmenti M0 sono 438, 503, 519, 495; per M1 362, 318, 250, 264. La scala M1 mostra non stazionarietà apparente. Con soli 32 campioni, tau, anisotropia reale/immaginaria e variazione temporale non sono stimati stabilmente; nessuno scenario è dichiarato vero.

## Partizione alternativa sui dati reali

Sul picco, il guadagno aggregato aumenta da 35.88% a **50.33%**; NMSE aggregata M0→M1 `0.240258→0.119341`. Migliorano 7/8 blocchi. `s_M1` dei training varia fra 0.397216 e 0.413135 rad/s (span 0.015918), CV di `|c|/|a|=0.0890`, nessun flag di stabilità. Il fit completo è lo stesso del 15D.

| Blocco test | NMSE M0 | NMSE M1 | Guadagno | s M1 training [rad/s] | |c|/|a| |
|---|---:|---:|---:|---:|---:|
| 0–3 | 0.932707 | 0.828018 | +11.22% | 0.413135 | 0.31369 |
| 4–7 | 0.208467 | 0.035672 | +82.89% | 0.400299 | 0.30704 |
| 8–11 | 0.083801 | 0.126216 | −50.61% | 0.397216 | 0.37395 |
| 12–15 | 0.206627 | 0.096710 | +53.20% | 0.402143 | 0.32241 |
| 16–19 | 0.186153 | 0.069624 | +62.60% | 0.402193 | 0.29123 |
| 20–23 | 0.141885 | 0.061927 | +56.35% | 0.400364 | 0.34181 |
| 24–27 | 0.268985 | 0.058830 | +78.13% | 0.408871 | 0.29843 |
| 28–31 | 0.872496 | 0.315066 | +63.89% | 0.409460 | 0.27281 |

Il risultato non dipende dalla sola partizione 4×8, benché un blocco interno peggiori. Sui 15 bin dipendenti, la classificazione primaria 4/7/4 (ripetuto/negativo/parziale) diventa 4/8/3. Restano positivi e stabili picco, 133,64, 136,65 e 137,66; 136,66 passa da +10.64% a −8.68%. Il comportamento non è uniforme né interpretabile come 15 componenti indipendenti.

## Nulli: distribuzione del vantaggio

La tabella usa la scala primaria M0, 300 repliche per riga. `>= reale` confronta separatamente con 35.88% nella partizione primaria e 50.33% nell'alternativa. `Congiunti` richiede anche tutti i fold migliorati e nessun flag di stabilità; è una frequenza empirica condizionata al nullo, non un p-value esatto.

| tau [s] | Partizione | mediana gain | q95 | Tutti i fold | >= reale | Congiunti |
|---:|---|---:|---:|---:|---:|---:|
| 0 | 4×8 | −9.05% | 10.35% | 16/300 | 0/300 | 0/300 |
| 0 | 8×4 purged | −8.16% | 5.87% | 0/300 | 0/300 | 0/300 |
| 0.5 | 4×8 | −11.10% | 12.74% | 8/300 | 0/300 | 0/300 |
| 0.5 | 8×4 purged | −11.32% | 12.46% | 0/300 | 0/300 | 0/300 |
| 2 | 4×8 | −16.54% | 44.46% | 24/300 | 26/300 | 15/300 |
| 2 | 8×4 purged | −19.39% | 35.16% | 3/300 | 8/300 | 2/300 |
| 5 | 4×8 | +3.72% | 75.04% | 64/300 | 101/300 | 60/300 |
| 5 | 8×4 purged | +5.74% | 72.29% | 22/300 | 60/300 | 22/300 |

Con scala alternativa M1 (100 per scenario), i congiunti sono 0/100 per tau 0 e 0.5; 6/100 e 1/100 per tau 2; **23/100** e **5/100** per tau 5, rispettivamente nelle due partizioni. Ridurre la scala non elimina l'effetto della correlazione lunga.

Le pendenze non sono mantenute fisse. Per la scala primaria, i quantili 5–50–95% di `s_M1−s_M0` sono circa:

- tau 0: −0.000536, −0.000009, +0.000505 rad/s;
- tau 0.5: −0.000778, +0.000003, +0.000990 rad/s;
- tau 2: −0.001772, +0.000037, +0.002352 rad/s;
- tau 5: −0.003251, −0.000016, +0.003296 rad/s.

La differenza reale −0.001707 rad/s è ordinaria nello scenario lungo e appena entro il 5% inferiore approssimativo dello scenario tau=2. Non è una firma specifica di offset. Le categorie `repeated_predictive_stable` sotto nullo crescono con tau: nella partizione primaria 15, 13, 44 e 80 su 300; nell'alternativa 0, 8, 20 e 56. La classificazione operativa del 15D non era calibrata come test statistico e può produrre falsi positivi sotto correlazione.

## Interpretazione e limiti

Il nullo iid o a correlazione breve non riproduce, in queste repliche, un risultato almeno altrettanto favorevole del picco. Il regime tau=2 s lo riproduce occasionalmente; tau=5 s lo riproduce spesso. Proprio la partizione purged, pur separando training e test di circa 2.1 s, non spezza una correlazione con scala 5 s. Il vantaggio reale resta robusto alla scelta fra le due partizioni, ma non al modello di rumore.

La conclusione richiesta è quindi: **risultato favorevole a M1 e robusto alla partizione esaminata, ma compatibile anche con una singola componente e rumore temporalmente correlato lungo**. I dati non distinguono statico deterministico, dinamica lenta non modellata e rumore persistente. Le frequenze 60/300 o 22/300 descrivono soltanto questa famiglia OU, i parametri nulli stimati dal dato e queste soglie; non sono probabilità di contaminazione di Vandenberg né p-value esatti.

Il modello nullo è nel dominio dei coefficienti Fourier dell'intensità, non un simulatore SAR raw phase-history. Non include speckle fisico, MTF, leakage spettrale, covarianza complessa rotante o non stazionarietà. La scala M0 può essere eccessiva perché ingloba l'offset apparente; la scala M1 può essere troppo piccola perché M1 assorbe struttura. I risultati appaiati fra scale non forniscono repliche indipendenti. Bin e fold reali restano dipendenti.

## Verifica, artefatti e decisione finale

Sono conservati configurazione e semi, 1600 risultati nulli compressi con entrambi i confronti, risultati reali, CSV delle distribuzioni e dei fold, summary JSON e tre figure: distribuzioni empirical-CDF, confronto partizioni e residui/ACF/non-stazionarietà. Non sono stati omessi fallimenti: sono zero. Un tentativo iniziale di multiprocessing è stato negato dalla sandbox Windows; è stato usato un ciclo sequenziale con identici seed, disegno e algoritmo. Una correzione di serializzazione `numpy.int64→int` ha interessato solo il riepilogo, dopo i fit. Queste due modifiche operative sono successive all'hash sorgente iniziale registrato nella configurazione; il manifest finale registra i sorgenti effettivamente eseguiti.

Test nuovi: covarianza OU su tempi irregolari e inizializzazione stazionaria; proprietà del caso iid e riproducibilità; supporto purged; invarianza dei parametri rispetto a modifiche dei campioni test/guard. Suite completa riportata nel manifest finale. Hash guards dei Block15B–D verificati; sorgenti radar non modificati.

Fra gli esperimenti proposti, il più utile successivo è la **verifica sintetica di separabilità fra componenti vicine**, con poche separazioni/rapporti prefissati e gli stessi tempi. Il confronto intensità lineare/logaritmica cambierebbe il preprocessing del dato reale e non risolverebbe il limite emerso: una struttura lenta rispetto a soli ~21.84 s può apparire statica o come rumore molto persistente. La separabilità verifica direttamente quando M1 assorbe una seconda componente quasi stazionaria senza identificarla come offset. È una proposta, non eseguita; richiede nuova motivazione/autorizzazione.

**STOP — Block15E completato.** Nessuna sottrazione, correzione, nuova formazione look, nuova lettura CPHD, inversione, download, sweep, commit o push. `T_SAR=17.902230457 s` e tutti i risultati congelati restano invariati.
