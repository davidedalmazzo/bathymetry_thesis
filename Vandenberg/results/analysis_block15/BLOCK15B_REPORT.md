# Block 15B — confronto controllato degli stimatori su BP12

2026-09-11. Completato, senza formazione di look, letture CPHD/SICD, download, inversione o sweep. Gli artefatti precedenti, compreso l'audit 15A, restano invariati. `T_SAR = 17.902230457 s` resta congelato: non viene sostituito dai risultati BP12 qui riportati.

## Esito in breve

Lo stimatore storico è riprodotto alla precisione numerica. La coerenza corretta modifica sostanzialmente la selezione, ma non elimina da sola tutti i bin con fase poco descrivibile da una retta. Sui 15 bin con validità comune, C (multi-lag) resta vicino ad A (OLS); B (consecutivi) presenta differenze più ampie e non uniformi. Al picco documentato tutti e tre sono validi secondo le regole congelate, ma non coincidono esattamente. Nessuno di questi esiti prova che la pendenza sia la frequenza oceanica.

## 1. Input, configurazione e riproducibilità

Input reale esclusivo: `../block12_backprojection/BLOCK12_SUBLOOKS_complex64.npy`, 9,584,768 byte, complex64, 32 × 288 × 130. Manifest BP12 e verifica PVP dell'audit concordano sui 32 centri medi TxTime: 0.3553473102–22.1915038278 s. Usata la lista reale, non una cadenza nominale. Durata dei look invariata, circa 0.7044 s, aperture disgiunte. Passo griglia 5 m, supporto 1440 × 650 m; passo non equivalente a PSF misurata.

`BLOCK15B_CONFIG.json` è stato scritto dal comando `prepare` **prima** del calcolo degli spettri BP12. Contiene identificazione stat/header dello stack, hash dei piccoli input congelati, tempi, griglia, codice, soglie, pesature e ricerca. Non contiene boa o DEM come input di selezione. Il riferimento storico JSON è letto soltanto per identificare il bin documentato; il confronto numerico usa anche la vecchia mappa delle pendenze, senza eseguire le inversioni presenti nel vecchio main.

Preprocessing esattamente riusato da `analyze_block12_phase_slope.py::tukey2d/detrended_spectrum`: `abs(z)**2` sul complex64, poi float64, rimozione del piano globale, Tukey separabile alpha 0.1, `fftshift(fft2)`. Nessuna intensità logaritmica, nuova ROI, padding, filtro di dispersione o normalizzazione aggiuntiva dei look. **Un solo stack Fourier alimenta A, B e C. La fase resta per singolo bin.**

Assi CSV: kx = k_parallel, ky = k_perpendicular in rad/m; non sono gli assi range/azimuth SICD. Il bearing di griglia è 79.8357237° dal nord UTM, non dal nord geografico vero. Riportati angolo relativo all'asse parallelo e bearing del vettore rispetto al nord della griglia. Non viene dedotta una nuova direzione oceanica.

### Regole congelate

- Banda 40–500 m; semipiano canonico kx<0 oppure kx=0, ky<0, per non contare due volte i coniugati.
- Potenza media >5% del massimo nella banda completa, calcolato senza gate di fase. Il bin storico (133,65) è sempre incluso come diagnostica, anche nell'eventualità di esclusione.
- MSC locale su patch 3×3 complete: `abs(mean(Fj*conj(Fi)))**2/(mean(abs(Fj)**2)*mean(abs(Fi)**2))`. Potenza nulla o campioni non finiti: valore 0 e flag invalid; bordi invalidi, niente wrap spaziale.
- Candidati comuni: potenza e banda sopra indicate, coefficienti finiti e non nulli in tutti i look, patch valida, **MSC endpoint >=0.09**, cioè 0.3², equivalente alla soglia in modulo del primo Block12. La soglia 0.25 del secondo script equivale invece a 0.0625: riportata separatamente, non scambiata con 0.25 MSC.
- MSC adiacente minima registrata come diagnostica, non usata per selezionare o pesare la fase. Nessun gate comune su R².
- A valido se massimo incremento wrapped <0.8π, RMSE unwrapped <=0.5 rad e pendenza interna alla ricerca. B/C validi se RMS circolare <=0.5 rad, minimo non al bordo e nessun altro minimo entro +0.01 di costo normalizzato. Flag separati dai candidati comuni; confronto conclusivo sull'intersezione.
- Differenza >0.02 rad/s: soglia descrittiva predefinita per contare divergenze, **non significatività statistica**. Gli altri limiti sono gate operativi, non soglie fisiche universali né ottimizzate sui risultati.

La MSC 0.09 è permissiva: con nove campioni complessi indipendenti la MSC nulla ha media circa 1/9; sui bin reali finestrati i campioni non sono indipendenti. Questa soglia conserva l'equivalenza storica, NON certifica significatività della coerenza.

## 2. Tre stimatori e interpretazione

Implementazione comune: `code/umbra_sar/frequency_comparison.py`.

**A:** `arg(Ft*conj(Fref))`, unwrap cronologico, OLS con intercetta libera sui tempi reali. Riferimento centrale indice 16; ripetizione ai riferimenti 0 e 31. La stima storica viene conservata anche se fallisce la nuova validità. Piccoli incrementi sono condizione di continuità, non prova assoluta contro una componente più veloce aliasata.

**B:** cross direttamente calcolati per le 31 coppie consecutive. Minimo di `sum w*[1-cos(delta_phi-s_phi*delta_t)]`, pesi uniformi e delta_t individuali. Nessuna divisione della fase media per un delta_t nominale.

**C:** stessa funzione obiettivo per lag 1,2,4,8: rispettivamente 31,30,28,24 coppie, totale 113. Ogni classe pesa 1/4; ogni coppia pesa 1/(4*N_lag). Le classi non dominano per numerosità, ma la sensibilità del costo alla pendenza contiene comunque delta_t²: pari peso di classe non significa pari informazione sulla pendenza.

Ricerca comune **[-3.2144510916,+3.2144510916] rad/s**, derivata esclusivamente da ±0.8π/max(delta_t adiacente). Griglia 2001 punti e raffinamento di ogni minimo locale, inclusi minimi di bordo; tutti registrati nel JSON dettagliato. È una restrizione esplicita al ramo lento accessibile con le cadenze disponibili, non una ricerca globale su qualunque frequenza possibile. I lag lunghi possono avere più minimi dentro lo stesso intervallo.

Si riportano `s_phi` con segno. `conditional_ocean_frequency` resta null: il modello necessario per chiamare questa pendenza omega oceanica non è identificato. Il solo modulo usato è quello del confronto diagnostico con l'omega storicamente salvata.

## 3. Riproduzione storica e selezione corretta

- Picco storico riprodotto: indice **(133,65)**, k_parallel = −0.04799655443 rad/m, k_perpendicular = 0, lambda = 130.9090909 m.
- Massima differenza sull'intera mappa signed rispetto al NPZ Block12: **4.44e-16 rad/s**. Maschera storica riprodotta identica. Differenza sul modulo al picco: 1.11e-16 rad/s.
- Il segno al bin scelto è **positivo**. Essendo il membro a k_parallel negativo della coppia coniugata, ciò non contraddice la convenzione né il segno del risultato congelato su un diverso input/bin. Non effettuare confronti fra moduli e pendenze signed senza esplicitarlo.

| Passaggio | Bin |
|---|---:|
| Banda e semipiano canonico | 915 |
| Potenza >5%, prima del gate MSC | 214 |
| Candidati comuni, MSC >=0.09 | 138 |
| Esclusi dal gate corretto rispetto ai 214 | 76 |
| Sensibilità puramente descrittiva a MSC >=0.0625 | 163 |
| A validi fra i 138 | 30 |
| B validi fra i 138 | 23 |
| C validi fra i 138 | 16 |
| Intersezione A/B/C e candidati comuni | **15** |

La coerenza degenere avrebbe fatto passare tutti i 214 candidati preliminari non nulli. La riduzione 214→138 isola il cambio di coerenza mantenendo gli altri criteri identici; non va confusa con il confronto fra i due vecchi script Block12, che avevano anche bande e soglie di potenza diverse.

## 4. Risultati al picco fissato

MSC endpoint **0.416882**; minima MSC adiacente **0.805906**. Picco mantenuto, valido per tutti i metodi.

| Metodo | s_phi [rad/s] | Diagnostica residui |
|---|---:|---|
| A, riferimento centrale | **+0.4120656492** | RMSE 0.200095 rad; R² 0.994456 |
| B, consecutivi | **+0.4322715136** | RMS circolare 0.118819 rad |
| C, lag 1/2/4/8 | **+0.4183342902** | RMS circolare 0.236167 rad |

B−A = +0.0202058644 rad/s (circa +4.90% di A); C−A = +0.0062686410 rad/s (circa +1.52%). Gli RMS non classificano automaticamente il metodo migliore: misurano residui diversi su differenti baseline.

Il massimo passo wrapped è 0.7123 rad: al picco non emerge ambiguità nell'unwrap con i baseline adiacenti. Cambiando riferimento la pendenza resta identica. La fase residua è strutturata, non una nuvola indipendente attorno alla retta; non viene corretta.

Una spiegazione **processistica dello scarto fra stimatori**, senza attribuzione oceanografica: la secante fra estremi è +0.4318250622 rad/s, vicina a B; la versione linearizzata del costo consecutivo dà +0.4327223969. Con campionamento regolare gli incrementi consecutivi telescopano e il fit locale si avvicina alla secante; A pesa la traiettoria temporale intera in modo diverso. La forma residua e i pesi temporali bastano quindi a produrre uno scarto A/B senza un errore di segno o di riferimento. Non dimostrano la causa fisica dei residui.

### Lag singoli: non scegliere silenziosamente un alias

| Lag | Delta_t medio [s] | Minimo globale s_phi | Esito |
|---|---:|---:|---|
| 1 | 0.704392 | +0.432272 | unico, valido |
| 2 | 1.408792 | +0.433900 | valido; bordi con costo molto maggiore |
| 4 | 2.817581 | +2.659949 | ambiguo |
| 8 | 5.635166 | +2.644095 | ambiguo |

Lag4 ha anche +0.430081 (costo 0.032652 contro 0.032302 del minimo globale) e −1.799781. Lag8 ha anche +1.529096, +0.414086, −0.700933, −1.815962, −2.931001, tutti entro il margine configurato dal migliore. Non si sceglie +0.430/+0.414 perché sembrano attesi: sono riportati come alternative. Il salto grafico a circa 2.65 rad/s **non prova dipendenza fisica dal baseline**. La combinazione C usa le classi corte per distinguere il minimo, senza riferimento esterno.

## 5. Localizzazione delle differenze e dipendenze

Sui 15 bin dell'intersezione:

| Scarto assoluto | Mediana [rad/s] | Massimo [rad/s] | Bin >0.02 rad/s |
|---|---:|---:|---:|
| B−A | 0.014768 | 0.041384 | 5/15 |
| C−A | 0.003646 | 0.010949 | 0/15 |

Lo scarto signed B−A varia da −0.016454 a +0.041384, mediana +0.007209; C−A da −0.010949 a +0.007779. **Non c'è un offset costante comune a tutti i bin.** Non viene fitatto o sottratto alcun termine di bias.

Prima della validità individuale, sui 214 bin le mediane degli scarti assoluti salgono a 0.06824 (B−A) e 0.04175 (C−A); massimi 3.34788 e 2.29083. Nei 76 esclusi per MSC le mediane sono 0.09075 e 0.05041. La bassa qualità è associata a divergenze maggiori, ma non è l'unica condizione: una MSC endpoint accettabile non implica fase temporale lineare.

Fra tutti i 214 valutati, 116 falliscono il guard di passo A, 172 il RMSE A; 180 falliscono il RMS B; 191 il RMS C e 6 hanno minimi C concorrenti. Le motivazioni possono sovrapporsi. I lag4 e lag8 singoli sono ambigui rispettivamente in 212 e 214 casi: non sono stime indipendenti robustamente branch-resolved.

Le divergenze estreme si concentrano fuori dall'insieme di buona qualità e anche in zone più oblique; le 15 accettate sono concentrate vicino al gruppo principale ma non soltanto a ky=0. In raggruppamenti descrittivi rispetto all'asse parallelo: 4 accettate su 38 entro 10°, 9/83 fra 10–30°, 2/93 oltre 30°. Non è una legge di bias in funzione dell'angolo: qualità, potenza, k e finestra sono confondenti, e 15 bin finestrati non sono 15 onde indipendenti.

Su tutti i 214, massimo span di pendenza fra riferimenti 0/16/31: **3.33e-16 rad/s**. Massimo errore di telescoping degli incrementi: **7.11e-15 rad**. Il riferimento non spiega le differenze. A al picco coincide inoltre con l'identità algebrica OLS espressa come somma su tutte le coppie; non è una nuova replica indipendente. Nessun intervallo di confidenza iid sulle coppie è stato prodotto.

## 6. Test e diagnostica sintetica

Prima dell'analisi reale: **11 test mirati passati** in 1.39 s. Testano componente isolata su tempi regolari e BP12, entrambi i segni, coniugazione/ordine cross, wrapping e fase iniziale, riferimenti, telescoping, MSC coerente/decorrelata/nulla, non finiti e bordi, pesi per lag e minimi alias. Semi rumore 1501/1502; tolleranza 1e-6 rad/s per raffinamento circolare e 1e-12 per OLS ideale, non incertezze geofisiche.

Aggiunto controllo ulteriore di fase iniziale circolare e raffinamento griglia 2001→4001 sul sintetico ideale. Suite finale: **69 passati, 0 falliti, 0 saltati**, inclusi 12 nuovi test e i precedenti 57 (SarPy compreso). Nessun test automatico CPHD end-to-end aggiunto: quel limite resta aperto.

Diagnostica sintetica registrata: `z(t)=exp(-i*0.61*t)+a_static*exp(i*0.4)` allo stesso k, ampiezze prefissate 0/0.5/1.4, tempi BP12. È un modello di coefficienti, non di formazione radar e non calibrato sui residui reali.

| Ampiezza statica | A | B | C | Osservazione |
|---|---:|---:|---:|---|
| 0 | −0.610000 | −0.610000 | −0.610000 | Recupero ideale |
| 0.5 | −0.618392 | −0.598471 | −0.624210 | Metodi diversi pur con stessa componente mobile |
| 1.4 | +0.012148 | −0.025881 | +0.018983 | Dominio quasi statico; A/C falliscono il gate residui, B passa |

La contaminazione può cambiare la pendenza osservata e la validità del modello senza cambiare la frequenza della componente mobile. Non è stato imposto il recupero di −0.61 nel caso ambiguo; l'esempio non prova che questa sia la contaminazione presente in BP12.

## 7. Decisione e minimo passo successivo

1. **Storico riprodotto? Sì**, inclusi picco, mappa e maschera diagnostica storica.
2. **MSC cambia i bin? Sì**, 76 dei 214 candidati preliminari esclusi; il picco fisso resta.
3. **Differenze localizzate o sistematiche?** Le grandi divergenze sono concentrate nei bin non validi; quelle residue A/B non sono nulle né un offset universale. C è più vicino ad A nell'intersezione, non per questo più vicino alla frequenza oceanica vera.
4. **Riferimento, unwrap, lag, qualità?** Riferimento ininfluente numericamente; unwrap problematico in molti bin ma non al picco; lag lunghi singoli fortemente aliasati. Al picco i diversi pesi temporali applicati a una fase non perfettamente lineare spiegano la sensibilità A/B.
5. **Ambiguità anche con accordo?** Origine oceanografica, presenza di contributi statici/lenti o più componenti allo stesso k, leakage spaziale, trasferimento SAR, risoluzione della PSF e correttezza dinamica della formazione CPHD non sono risolti dall'accordo di tre trasformazioni degli stessi dati.
6. **Minimo esperimento successivo:** estendere moderatamente la **contaminazione sintetica allo stesso k**, mantenendo tempi e stimatori congelati e introducendo poche ampiezze/fasi e un contributo lento prefissati. Confrontare la forma dei residui e i costi per lag, non soltanto una pendenza media; includere un controllo statico puro. È più informativo ora di cambiare simultaneamente intensità lineare/logaritmica o avviare shoaling/separabilità: qui è emersa sensibilità ai pesi temporali anche con unwrap continuo, e il piccolo esempio sintetico mostra già una possibile non-identificabilità. Non tarare parametri per riprodurre il valore reale; tale eventuale esperimento richiede nuova autorizzazione.

## 8. Artefatti e comandi

- `BLOCK15B_CONFIG.json`: configurazione precedente all'analisi.
- `BLOCK15B_MANIFEST.json`: manifest dell'esecuzione iniziale e guardie dei congelati.
- `BLOCK15B_BINS.csv`: 915 bin canonici, flag ed esclusioni; stime vuote quando non valutate, non zero.
- `BLOCK15B_SUMMARY.json`: riproduzione, conteggi e confronto.
- `BLOCK15B_ESTIMATOR_DETAILS.json`: fasi, residui, delta_t, pesi e tutti i minimi per i 214 bin valutati.
- `BLOCK15B_SYNTHETIC_CONTAMINATION.json` e `BLOCK15B_DIAGNOSTICS.json`: diagnostiche complete e riassunti descrittivi.
- `BLOCK15B_COMPARISON.png`: confronto sull'intersezione e mappe delle divergenze, cerchi sugli esclusi.
- `BLOCK15B_FIXED_PEAK.png`: fase, residui, lag e obiettivo circolare completo al picco.
- `BLOCK15B_LAG_DEPENDENCE.png`: minimi per lag, da leggere insieme ai flag di ambiguità, non come curva fisica.
- `BLOCK15B_VALID_BINS_AND_MIXTURE.png`: mappa delle differenze valide su scala più fine e diagnostica sintetica. Figure controllate visivamente; titolo della figura supplementare accorciato senza cambiare dati/configurazione.
- `BLOCK15B_DELIVERY_MANIFEST.json`: verifica finale, test e provenienza dei file supplementari.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv-umbra-thesis\Scripts\python.exe -B -m pytest tests/test_frequency_comparison.py -q -p no:cacheprovider
.\.venv-umbra-thesis\Scripts\python.exe -B code/analyze_block15b_frequency.py prepare
.\.venv-umbra-thesis\Scripts\python.exe -B code/analyze_block15b_frequency.py run
.\.venv-umbra-thesis\Scripts\python.exe -B code/summarize_block15b_diagnostics.py
.\.venv-umbra-thesis\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
```

I comandi di generazione rifiutano file risultati già presenti; non rilanciarli sopra questi artefatti. `--plot-only` nel riepilogo rigenera esclusivamente la figura supplementare. Nessun commit o push eseguito. Stop al completamento Block15B.
