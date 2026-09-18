# Block 15C — contaminazione statica/lenta e stima della frequenza

Concluso il 2026-09-12. Esperimento esclusivamente sintetico nel dominio dei coefficienti Fourier dell'intensità. Nessuna lettura dello stack reale, correzione BP12, formazione radar, inversione, download o sweep. Risultati Block15A/B e `T_SAR=17.902230457 s` invariati.

## 1. Verifica documentale: 138 candidati → 15 comuni

Ricostruita dal CSV Block15B, senza cambiare soglie o rieseguire selezioni. I conteggi si riferiscono ai **138 candidati comuni**, non ai 214 bin preliminari. Dettaglio completo e intersezioni in `BLOCK15C_ATTRITION_AUDIT.json`.

| Motivo | Esclusi fra 138 |
|---|---:|
| A: RMSE unwrapped >0.5 rad | 108 |
| A: incremento wrapped >=0.8π | 74 |
| B: RMS circolare >0.5 rad | 115 |
| C: RMS circolare >0.5 rad | 122 |
| C: minimo alternativo entro il margine configurato | 3 |
| A fuori intervallo, B/C al bordo, ambiguità B | 0 |

Le 74 esclusioni per incremento A sono tutte già escluse dai residui A/B/C. Le 3 ambiguità C ricadono anch'esse nelle esclusioni per residui: non aggiungono tre bin alla perdita totale. Sovrapposizioni dei fallimenti residui: A∩B=107, A∩C=108, B∩C=114; A∩B∩C=107. Unione=123, quindi 138−123=15.

| Pattern esatto di validità | Bin |
|---|---:|
| A/B/C tutti validi | 15 |
| Solo A e B | 7 |
| Solo A e C | 1 |
| Solo A | 7 |
| Solo B | 1 |
| Nessuno valido | 107 |

Il collo di bottiglia è soprattutto la qualità della descrizione temporale, non una semplice ambiguità di ramo. La MSC aveva già ridotto 214→138. R² non era un gate del Block15B. Confermati documentalmente la riproduzione storica, le pendenze al picco A/B/C +0.412066/+0.432272/+0.418334 rad/s, l'invarianza dal riferimento e l'ambiguità dei lag singoli 4/8. Nessuno di quei valori è un bersaglio della simulazione.

## 2. Disegno congelato e convenzioni

`BLOCK15C_CONFIG.json` è stato salvato prima della griglia. Richiama direttamente le funzioni congelate di `frequency_comparison.py` e conserva i 32 tempi effettivi BP12, senza cadenza nominale. A è l'OLS con riferimento centrale; B usa cross consecutivi diretti; C usa lag 1/2/4/8 con pari peso totale per classe. Restano invariati ricerca ±3.2144510916 rad/s, griglia 2001 punti, raffinamento dei minimi, margine di ambiguità 0.01, limiti di residui e unwrap.

Modello, con A=1 e phi_A=0:

`F(t)=exp(i*s_true*t)+r*exp(i*s_cont*t+i*delta_phi)+epsilon(t)`.

- s_true = 0.3, 0.5, 0.7 rad/s; r=B/A = 0, 0.25, 0.5, 1, 2.
- s_cont/s_true = 0, −0.2, +0.2; delta_phi = 0,π/4,…,7π/4.
- Omesse soltanto le duplicazioni di fase e s_cont quando r=0: **291 configurazioni**.
- Prima 291 casi senza rumore, poi sigma=0.1 e 0.3 con **50 repliche per configurazione e livello**: 14,550+14,550; totale **29,391**.
- Rumore complesso circolare: `E|epsilon|²=sigma²`, varianza di ciascuna parte reale/immaginaria sigma²/2. Normalizzazione rispetto ad A, non all'ampiezza totale della miscela.
- Seed: `SeedSequence([150300,case_id,noise_index,replicate])`. Repliche indipendenti; stessa realizzazione per A/B/C. I confronti fra metodi sono appaiati, le coppie temporali interne non sono repliche indipendenti.

r è un **rapporto di ampiezze dei coefficienti**, non di energie. A identifica la componente bersaglio anche quando B>A: in quel regime il contaminante è energeticamente dominante. Un fallimento nel recuperare A non implica automaticamente un bug nello stimatore a componente unica.

La convenzione resta `F_secondary*conj(F_reference)`: per una sola componente si recupera s_true. Questi F rappresentano un **bin spaziale non nullo**; il termine statico non è la media spaziale dell'immagine. Sottrarre media/piano a ogni immagine non elimina necessariamente tale struttura. Il modello non simula CPHD, formazione SAR, speckle completo, MTF, né immagini fisicamente generate. Nessuna frequenza è stata scelta per avvicinarsi ai valori reali o alla boa.

## 3. Verifiche analitiche

Senza rumore, indicando theta=(s_true−s_cont)t−delta_phi:

`s_inst = [s_true + r²*s_cont + r*(s_true+s_cont)*cos(theta)] / [1+r²+2*r*cos(theta)]`.

È l'identità `Im(conj(F)*dF/dt)/|F|²`, verificata anche per differenze finite. Distingue la pendenza della componente, quella istantanea della miscela e la regressione sul record finito.

- B=0: recupero di s_true.
- Stessa pendenza dei due contributi: componente unica equivalente, salvo cancellazione.
- Contaminante statico: `s_inst=s_true*(1+r*cos(theta))/(1+r²+2r*cos(theta))`; dipendenza da ampiezza e fase, non riduzione necessariamente costante.
- Per r vicino a uno, quasi-cancellazioni possono amplificare il rapporto e rendere la fase instabile. A r=1 la derivata regolare, dove definita, non descrive i salti di fase attraverso gli zeri.
- Coniugazione e inversione simultanea di segni/fasi invertono le pendenze.

Le diagnostiche analitiche usano anche 2049 campioni temporali densi per ciascun caso senza rumore. Sotto |F|=1e-12 la derivata è marcata indefinita; questa soglia diagnostica **non modifica i gate degli stimatori**. La media della derivata sui punti finiti non è presentata come variazione netta di fase quando esistono cancellazioni.

## 4. MSC: due intorni sintetici espliciti

Intorno 3×3, u,v∈{−1,0,1}; profilo principale:

`h=exp(-(u²+v²)/4)*exp(i*(0.3u−0.2v))`.

Due ipotesi per il contaminante:

1. **Proporzionale:** q=h.
2. **Diverso:** `q=h*(1+0.4u+0.2v)*exp(i*0.7*(u−v))`.

Al centro h=q=1: stessa serie per gli stimatori. Ogni vicino riceve rumore indipendente in tempo e spazio, di uguale varianza assoluta; le due geometrie riusano lo stesso rumore per un confronto appaiato. La MSC è calcolata dalla funzione Block15B sui nove coefficienti dei look primo/ultimo, non da un singolo prodotto. Non si attribuisce questa struttura al lobo reale.

Nel caso proporzionale senza rumore ogni patch temporale è un multiplo dello stesso vettore h: la **MSC vale uno anche quando la miscela ha una pendenza distorta**. È una proprietà della coerenza spaziale, non una verifica della frequenza della componente A. Un profilo diverso riduce la coerenza in alcuni casi, ma non sempre. Con rumore il maggiore r aumenta anche il rapporto segnale totale/rumore, poiché sigma è normalizzata ad A.

## 5. Evento centrale e frequenza di occorrenza

Definizione registrata prima della griglia: esiste almeno una coppia di metodi che siano **entrambi validi secondo Block15B**, entrambi con errore relativo assoluto **>10%**, e con pendenze signed distanti **<=0.02 rad/s**. È una soglia descrittiva, non un test di significatività. Si riportano anche distribuzioni continue e risultati non accettati.

Qualità supplementari, senza cambiare l'accettazione: R² di A>=0.97; MSC endpoint>=0.8. R² è specificamente quello di A anche quando la coppia concorde è un'altra.

| Rumore RMS/A | Tutte le simulazioni | Evento centrale | +R² alto e MSC proporzionale alta | +R² alto e MSC diversa alta |
|---|---:|---:|---:|---:|
| 0 | 291 | **76 (26.12%)** | 8 | 3 |
| 0.1 | 14,550 | **3,773 (25.93%)** | 255 | 141 |
| 0.3 | 14,550 | **3,433 (23.59%)** | 48 | 37 |

Tutti i denominatori sono le simulazioni della riga, non soltanto i casi accettati. Le percentuali descrivono **questo disegno**, non la probabilità di contaminazione oceanica. I 50 campioni sono repliche per configurazione; configurazioni differenti non hanno una distribuzione naturale di probabilità. Non sono prodotti intervalli iid dalle coppie temporali.

Senza rumore, eventi per rapporto: 0/3 a r=0; 0/72 a r=0.25; **5/72 a r=0.5**; 2/72 a r=1; **69/72 a r=2**. Dei 76 eventi, 22 hanno contaminante statico, 24 lento contro-rotante e 30 lento co-rotante, ciascuna classe su 96 casi contaminati. Il risultato non riguarda quindi soltanto contaminanti più forti del segnale bersaglio.

### Esempio selezionato senza taratura

La configurazione prescrive il primo caso senza rumore, in ordine di griglia, che soddisfa evento centrale, R²>=0.97 e MSC proporzionale>=0.8. È il **caso 29**: s_true=0.3, r=0.5, s_cont=0, delta_phi=π.

| Metodo | Pendenza [rad/s] | Errore relativo signed |
|---|---:|---:|
| A | +0.261144 | −12.95% |
| B | +0.310015 | +3.34% |
| C | +0.267819 | −10.73% |

Tutti i metodi sono validi; A e C concordano entro 0.00668 rad/s ma sono entrambi distorti oltre il 10%. A ha R²=0.978168 e RMSE=0.253724 rad; MSC proporzionale=1, MSC diversa=0.966688. Minimo |F|=0.501169: non è una quasi-cancellazione estrema. CV dell'ampiezza=0.350023 segnala comunque una modulazione. L'esempio dimostra una possibilità del modello, non una spiegazione di Vandenberg.

## 6. Tutti i risultati e selezione: nessun vantaggio da sopravvivenza

| Rumore | A accettati / totale | B accettati / totale | C accettati / totale |
|---|---:|---:|---:|
| 0 | 221/291 | 221/291 | 215/291 |
| 0.1 | 11,050/14,550 | 11,900/14,550 | 9,903/14,550 |
| 0.3 | 10,696/14,550 | 10,998/14,550 | 7,094/14,550 |

| Rumore | A: mediana errore relativo assoluto, tutti / accettati | B: tutti / accettati | C: tutti / accettati |
|---|---:|---:|---:|
| 0 | 16.94% / 3.25% | 10.41% / 4.00% | 10.73% / 3.76% |
| 0.1 | 7.83% / 3.10% | 10.19% / 4.68% | 8.01% / 3.90% |
| 0.3 | 7.88% / 3.60% | 13.40% / 6.32% | 8.37% / 3.97% |

Il miglioramento apparente delle mediane non condizionate di A/C introducendo rumore non prova un beneficio: i casi esattamente bilanciati r=1 hanno singolarità e unwrap molto sensibili. Sono distribuzioni miste, non una legge monotona di accuratezza.

A r=1 senza rumore tutti i metodi accettano soltanto 2/72 casi. A r=2 A e B accettano invece 72/72 e C 69/72, pur con bias spesso dell'ordine dell'intera pendenza bersaglio. Con sigma=0.3 e r=0.5 C accetta il 25.17%, contro circa il 90% di A/B: non va dichiarato superiore mostrando solo i sopravvissuti. Quantili, errori signed, esclusioni e minimi alternativi sono conservati per ogni realizzazione.

Anche gli errori positivi sono presenti: senza rumore i massimi errori signed sono circa +0.04576/+0.04602/+0.04055 rad/s per A/B/C. Il modello non supporta l'assunzione di una correzione negativa costante.

## 7. Diagnostiche: cosa segnala e cosa fallisce

Gli alert sono prefissati e descrittivi: CV ampiezza>0.3; minimo ampiezza<0.1; R² A<0.97; almeno un metodo invalido; spread A/B/C>0.02 rad/s; differenza fra RMS delle classi di lag del fit C>0.2 rad; MSC<0.8.

| Alert | Eventi segnalati senza rumore, su 76 | Con sigma=0.3, su 3,433 | Falsi alert su controlli senza contaminante, sigma=0.3, su 150 |
|---|---:|---:|---:|
| CV ampiezza>0.3 | 63 | 3,031 | 0 |
| Minimo ampiezza<0.1 | 1 | 7 | 0 |
| R² A<0.97 | 68 | 3,255 | 0 |
| Almeno un metodo invalido | 0 | 755 | 0 |
| Spread fra tre stimatori>0.02 | 42 | 1,782 | 27 |
| Spread RMS fra lag>0.2 | 70 | 3,057 | 0 |
| MSC proporzionale<0.8 | 0 | 488 | 102 |
| MSC diversa<0.8 | 23 | 1,388 | 102 |

Nessun singolo indicatore riconosce tutti gli eventi. Residui e variabilità d'ampiezza sono utili in questo modello; una soglia quasi-zero da sola perde quasi tutti i casi apparentemente affidabili. La MSC proporzionale fallisce per costruzione, mentre quella diversa non è comunque sufficiente. L'accordo di due metodi può coesistere col disaccordo del terzo.

Le somme/unioni di alert presenti nel JSON sono esplorative, non un classificatore validato; inoltre combinare indicatori delle due patch alternative non equivale a osservare due misure indipendenti del lobo reale. Non dedurre robustezza universale da questo disegno ristretto o dai tre controlli deterministici senza rumore.

I lag 2/4/8 singoli sono stimati separatamente nei **291 casi senza rumore**; minimi e ambiguità restano registrati. Nel Monte Carlo si riporta invece la diagnostica dei residui di ciascuna classe nel fit C: non viene chiamata una nuova stima indipendente di frequenza per lag. I minimi dei lag lunghi non sono risolti scegliendo il ramo più vicino alla verità sintetica.

## 8. Limiti e conclusioni richieste

1. **Quali contaminazioni possono ingannare?** Sia statiche sia lente, soprattutto se dominanti, ma anche r=0.5 in particolari fasi/record finiti. Due stimatori validi possono concordare su una pendenza distorta con R² e MSC elevati.
2. **Quali diagnostiche funzionano?** CV ampiezza, struttura residua e dipendenza dei residui dal lag segnalano molti casi, non tutti. MSC e accordo da soli falliscono; le soglie non sono trasferibili automaticamente al radar reale.
3. **Quanto differiscono A/B/C?** Il confronto dipende dal rapporto, dalla fase, dal rumore e dai gate. A/C possono condividere un bias mentre B è più vicino alla componente, come nel caso 29; in altri casi accade diversamente. C scarta molti più casi rumorosi. Non esiste un vincitore universale dimostrato.
4. **Limiti del modello:** due contributi deterministici allo stesso k, profili spaziali prescritti, rumore bianco additivo e tempi fissati. Mancano speckle dinamico, MTF, leakage da componenti vicine, correlazione temporale del rumore e formazione SAR. Il target A può essere meno energetico di B. Non è una validazione dell'inversione oceanografica o della formazione CPHD.
5. **Piccolo esperimento reale più discriminante:** su pochi bin BP12 già fissati e senza modificare i dati, descrivere la traiettoria del coefficiente complesso nel piano Re/Im insieme ad ampiezza, residui e rapporti complessi nei nove bin vicini. Verificare se una struttura persistente/coerente dell'intorno e la modulazione d'ampiezza sostengano o indeboliscano l'ipotesi di miscela, controllando anche la sensibilità agli estremi del record. È una proposta, non eseguita qui; non sottrarre un centro o una media temporale e non correggere la pendenza. Un modello a due contributi potrebbe comunque essere non identificabile su questo record.

Non si conclude che la contaminazione spieghi Vandenberg. Il meccanismo è possibile e suggerisce controlli diagnostici. La sottrazione del contaminante noto è verificata solo come identità in un test sintetico; lo stesso test mostra che la media temporale della componente mobile su un record finito può essere non nulla. **Nessuna rimozione automatica della media temporale reale.**

## 9. Artefatti, test e comandi

Nuovi file nella cartella corrente:

- `BLOCK15C_CONFIG.json`, `BLOCK15C_ATTRITION_AUDIT.json` e `BLOCK15C_RUN_MANIFEST.json`;
- `BLOCK15C_RESULTS.csv`: tutte le 29,391 realizzazioni, errori, validità, esclusioni, minimi, qualità, ampiezza e MSC;
- `BLOCK15C_RESIDUALS.npz`: residui A/B/C per realization_id, float32 solo per archiviazione; fit in float64;
- `BLOCK15C_AGGREGATES.csv`: 873 gruppi configurazione/livello di rumore; distribuzioni complete e denominatori in `BLOCK15C_SUMMARY.json`;
- `BLOCK15C_ANALYTIC_NOISELESS.json`, `BLOCK15C_EXAMPLES.json`;
- figure `BLOCK15C_BIAS_PHASE.png`, `BLOCK15C_ACCEPTANCE.png`, `BLOCK15C_QUALITY_MSC.png`, `BLOCK15C_EXAMPLES.png`, controllate visivamente;
- report e `BLOCK15C_DELIVERY_MANIFEST.json` finale.

Gli esempi temporali seguono i criteri congelati: cinque combinazioni statiche fissate a s_true=0.5 e il primo evento qualificato in ordine di griglia. La heatmap usa la sezione prefissata s_true=0.5 senza rumore; il caso r=0 è ripetuto graficamente fra le fasi ma non contato più volte nelle statistiche.

Prima della griglia: **10 nuovi test passati**, incluse proprietà analitiche, cancellazione, varianza del rumore, coerenza e segni. Suite completa: **79 passati, 0 falliti, 0 saltati**, con i precedenti 69 invariati. Il calcolo della griglia è durato circa 166 s; nessuna chiamata ai radar reali.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv-umbra-thesis\Scripts\python.exe -B -m pytest tests/test_contamination_diagnostic.py -q -p no:cacheprovider
.\.venv-umbra-thesis\Scripts\python.exe -B code/analyze_block15c_contamination.py prepare
.\.venv-umbra-thesis\Scripts\python.exe -B code/analyze_block15c_contamination.py run
.\.venv-umbra-thesis\Scripts\python.exe -B code/summarize_block15c_contamination.py
.\.venv-umbra-thesis\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
```

La generazione rifiuta gli output numerici esistenti. Un successivo `--plot-only` ha reso distinti colori/stili delle curve senza cambiare numeri, soglie o configurazione. WORKLOG aggiornato in append. Nessun commit o push. **Stop al Block15C.**
