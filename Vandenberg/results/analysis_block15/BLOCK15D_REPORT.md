# Block 15D — offset statico nei coefficienti BP12

Completato il 2026-09-12. Diagnostica di due modelli, non correzione della frequenza né identificazione fisica del contaminante.

## Esito principale

Sul picco fissato BP12 (133,65), il modello M1 con offset riduce del **35.88%** l'errore quadratico predittivo aggregato rispetto a M0 e migliora tutti e quattro i blocchi temporali esclusi. I parametri sono stabili secondo i criteri operativi prefissati. Questo dimostra utilità predittiva dell'offset nel modello adottato, non la presenza certa di un contributo fisicamente statico: anche contaminazione lenta e rumore correlato senza offset possono favorire M1 nei controlli sintetici.

## Dati, campione e invarianti

Usato esclusivamente lo stack BP12 esistente, aperto read-only: 32 look complessi, griglia 288 × 130, passo 5 m e supporto 1440 × 650 m. Tempi effettivi invariati dal Block15B, intervallo tra primo e ultimo centro circa 21.84 s. Questi tempi non sono la processed aperture duration SICD (18.068061721 s), né vanno confusi con il dwell CPHD disponibile (22.540812513 s).

Intensità lineare `abs(complex64)**2`, detrending planare globale in float64, Tukey 0.1 e Fourier spaziale: richiamate direttamente le funzioni già usate dal Block15B. Coefficienti complessi originali, senza normalizzazione a modulo unitario. MSC locale 3 × 3 invariata; non usata la coerenza degenere di un singolo prodotto. Nessuna sottrazione di media temporale o offset ai dati reali.

Il picco è già incluso nei 15 bin validi per tutti gli stimatori B: l'unione contiene quindi 15, non 16 bin. Nessuna riselezione dopo il fit. Il campione non contiene coppie coniugate; i coniugati sono solo controlli numerici. Errore relativo massimo sulla coniugazione dei coefficienti: 3.48e-16; massimo errore di chiusura `s(k)+s(-k)`: 6.45e-11 rad/s. Preservata `F_secondary * conj(F_reference)`. Il segno positivo sul rappresentante scelto non modifica convenzioni o risultati precedenti.

Dipendenza: delle 105 coppie di bin, 35 condividono celle della patch MSC e 68 hanno modulo della correlazione complessa temporalmente centrata >0.8. Quest'ultima centratura è solo una statistica di dipendenza, non preprocessing del fit. Bin, patch e fold non sono repliche indipendenti. Il campione pre-selezionato dal Block15B non rappresenta tutto lo spettro.

## Procedura fissata prima dei risultati reali

Con `tau=t-t0` e `t0` pari alla media dei tempi, confrontati soltanto:

- M0: `F=a exp(i s tau)+epsilon`, tre parametri reali;
- M1: `F=a exp(i s tau)+c+epsilon`, cinque parametri reali.

Per ogni s, a e c sono risolti linearmente sui soli campioni di training. Profilo globale su [-3.21445109155,+3.21445109155] rad/s, 2001 punti, intervallo del Block15B indipendente da boa/DEM. Raffinamento di tutti i minimi locali individuati dalla griglia, conservando alternative e bordi. Nessuna inizializzazione sulla frequenza preferita. In M1 a s=0 le colonne coincidono: rango e condizionamento segnalano la degenerazione. Un profilo piatto non viene presentato come soluzione identificata.

Quattro holdout consecutivi di otto look, indici 0–7, 8–15, 16–23 e 24–31. Tutti i parametri sono ristimati sui restanti 24; estremi = estrapolazione, interni = interpolazione. NMSE = somma |errore|² / somma |F osservato|² sul test. Guadagno aggregato = 1 − somma SSE(M1)/somma SSE(M0), non media semplice dei guadagni dei fold. Nessun p-value da quattro fold dipendenti.

Criteri in BLOCK15D_CONFIG.json, scritti prima di sintetici e dati reali: vantaggio ripetuto richiede guadagno aggregato almeno 10%, almeno tre fold migliorati e miglioramento a entrambi gli estremi. Stabilità richiede assenza di alternative entro 0.01 del costo normalizzato minimo, soluzioni non al bordo, rango pieno/condizionamento ≤1e6, larghezza del bacino a costo minimo+0.01 ≤0.2 rad/s, escursione di s fra fit completo e quattro training ≤0.05 rad/s, CV del rapporto |c|/|a| ≤0.5 e dispersione complessa di c rispetto al fit completo, normalizzata a |a_full|, ≤0.25.

Queste soglie sono diagnostiche, non intervalli di confidenza. Guadagno ≤0: `no_predictive_advantage`; ripetizione e stabilità: `repeated_predictive_stable`; gli altri casi positivi: `descriptive_or_unstable`. Quest'ultima etichetta include vantaggi non ripetuti anche con parametri stabili.

## Picco fissato: risultati continui

Bin (133,65), kx=-0.04799655443 rad/m, ky=0, lambda=130.9091 m; MSC agli estremi 0.416882.

| Quantità | M0 | M1 |
|---|---:|---:|
| s [rad/s] | +0.40607604 | +0.40436881 |
| a complesso | -261.293 + 1189.151i | -309.415 + 1260.437i |
| c complesso | 0 | -219.328 + 329.124i |
| Rapporto moduli c/a | 0 | 0.304740 |
| SSE training | 7,676,090.14 | 2,910,711.66 |
| NMSE predittiva aggregata | 0.226091 | 0.144975 |
| Larghezza bacino diagnostica [rad/s] | 0.035359 | 0.032145 |

Le unità di a e c sono quelle dei coefficienti FFT non normalizzati, non elevazione oceanica. La riduzione training del 62.08% da sola non costituisce evidenza: M0 è contenuto in M1.

| Test escluso | Tipo | NMSE M0 | NMSE M1 | Guadagno | s M1 [rad/s] |
|---|---|---:|---:|---:|---:|
| 0–7 | estremo | 0.605645 | 0.409022 | 32.47% | 0.416544 |
| 8–15 | interno | 0.151715 | 0.117403 | 22.62% | 0.398586 |
| 16–23 | interno | 0.148874 | 0.084298 | 43.38% | 0.399884 |
| 24–31 | estremo | 0.352575 | 0.190956 | 45.84% | 0.415574 |

Escursione di s completo+holdout: 0.017957 rad/s; CV(|c|/|a|)=0.0982; dispersione normalizzata di c=0.0773. Nessun flag di instabilità. La predizione rimane imperfetta, soprattutto al primo estremo (NMSE 0.409): un offset non spiega tutta la variabilità osservata.

La variazione M1−M0 è appena -0.001707 rad/s. Lo stimatore A storico restituisce +0.41206565 rad/s: A minimizza residui di fase, questi modelli minimizzano residui complessi e quindi non devono coincidere. Nessun valore è chiamato frequenza corretta. Il risultato congelato Block4 `T_SAR=17.902230457 s` resta intatto; non si convertono queste nuove pendenze in periodi oceanici.

## Distribuzione fra bin e casi contrari

| Bin | Guadagno predittivo M1 | Categoria |
|---|---:|---|
| 133,65 (picco) | +35.88% | ripetuto/stabile |
| 129,62 | -23.98% | nessun vantaggio |
| 129,63 | -40.02% | nessun vantaggio |
| 130,63 | -12.46% | nessun vantaggio |
| 131,60 | -36.74% | nessun vantaggio |
| 131,64 | -9.07% | nessun vantaggio |
| 132,65 | -50.86% | nessun vantaggio |
| 133,64 | +30.32% | non ripetuto agli estremi |
| 133,66 | +20.95% | non ripetuto agli estremi |
| 134,62 | -41.08% | nessun vantaggio |
| 134,66 | +34.86% | non ripetuto agli estremi |
| 135,66 | +9.26% | sotto soglia e solo due fold migliorati |
| 136,65 | +82.11% | ripetuto/stabile |
| 136,66 | +10.64% | ripetuto/stabile, marginale |
| 137,66 | +30.41% | ripetuto/stabile, un interno peggiora |

Quattro casi ripetuti/stabili, sette negativi, quattro intermedi. Nei quattro intermedi i parametri passano i controlli di stabilità: fallisce la ripetizione predittiva, non l'identificabilità numerica. (136,66) è vicino al gate del 10%; (137,66) peggiora di circa 149% nel primo fold interno, pur migliorando gli altri tre. Queste qualificazioni impediscono di interpretare il conteggio come successo uniforme. Il vicino (132,65), contrario all'ipotesi, peggiora del 50.86%.

Nei 75 fit M1 reali (15 completi e 60 training) non emergono profili piatti, alternative entro la tolleranza o bordi; larghezza massima 0.06750 rad/s. Il rapporto di offset è instabile nei bin 129,62; 129,63; 134,62. I profili e i holdout sostengono identificabilità operativa condizionata al modello su alcuni bin, non identificazione fisica. Il record contiene solo circa 1.4 cicli alla pendenza del picco: un contributo lento può apparire quasi statico.

## Controlli sintetici e interpretazioni concorrenti

Prima dei dati reali: sei test mirati, poi 44 controlli ai tempi BP12. Pendenza principale 0.5 rad/s e fase 0.3, indipendenti dal risultato reale. Quattro casi: singola componente; offset 0.5 exp(0.8i); modulazione di ampiezza `1+0.4 cos(0.08 tau+0.5)` senza offset; contaminante lento `0.5 exp(i(0.1 tau+0.8))`. Per caso: un controllo senza rumore, cinque white e cinque AR(1) complessi circolari con RMS 0.1. AR(1) stazionario in indice look, rho=0.8, innovazioni scalate sqrt(1-rho²); stessa realizzazione per M0/M1. SeedSequence [150400, caso, tipo rumore, replica]. Sono modelli di coefficienti d'intensità, non simulatori SAR raw phase-history.

| Verità sintetica | Casi | M1 ripetuto/stabile |
|---|---:|---:|
| Singola, nessun offset | 11 | 1 |
| Offset statico noto | 11 | 11 |
| Ampiezza lenta, nessun offset | 11 | 0 |
| Contaminante lento | 11 | 5 |

Nel singolo AR(1), replica 0, M1 migliora del 16.17%, con |c|/|a|=0.03293 e parametri operativamente stabili pur senza offset vero: una spiegazione concorrente esplicita. Cinque casi lenti passano gli stessi criteri. Il controllo AM scelto non passa, ma non esclude tutte le modulazioni o trasferimenti variabili.

Avvertenza numerica: nel singolo caso esatto senza rumore entrambi i modelli hanno errore trascurabile (NMSE circa 1.35e-17 e 8.73e-20). Il guadagno relativo vicino a uno è privo di significato pratico; c/a circa 1.9e-11 e instabilità relativa di un offset nullo producono l'etichetta intermedia. Non è evidenza a favore di M1. Il recupero esatto di s, a, c è verificato dai test, inclusi rango degenere, profilo piatto, bordo e coniugazione.

Dal Block15C restano validi 76/291 casi senza rumore con stime concordi ma distorte, otto anche con R² e MSC elevati. Residui di fase, variabilità d'ampiezza e dipendenza dai lag sono utili in alcuni casi, ma nessuno discrimina universalmente: in particolare MSC su profili proporzionali resta alta anche con bias. Né quei conteggi né questi 44 controlli stimano probabilità di contaminazione nella scena reale.

## Artefatti, verifica e risposte finali

Configurazione, tabella completa per bin e fold, SUMMARY e RESULTS JSON conservano coefficienti, residui complessi, predizioni, profili completi e minimi alternativi. SYNTHETIC JSON conserva gli stessi dettagli per i 44 controlli. Figure: TRAJECTORIES_1–5 mostrano tutti i 15 bin, picco per primo, modulo, fase/residui A e stime storiche per lag; PHASE_DIFFERENCES mostra i prodotti complessi ai lag 1,2,4,8 senza nuovo unwrapping; COST_PROFILES, PREDICTIVE e FIXED_PEAK completano la diagnostica. Nessuna selezione grafica a posteriori dei soli successi.

Suite completa nell'interprete `.venv-umbra-thesis`: **85 passed in 18.24 s**, nessun fallimento o skip. Sei test nuovi erano già passati prima dell'applicazione. Controllati gli hash degli artefatti A–C e dei sorgenti storici elencati nella configurazione; verificati dimensione e mtime dello stack. Il manifest di consegna registra gli artefatti nuovi. Nessun nuovo processamento CPHD, download, filtro di dispersione, sweep, inversione, commit o push.

1. **Picco:** sì, vantaggio predittivo M1 del 35.88%, presente anche nei due test agli estremi.
2. **Localizzazione:** non esclusivo del picco, ma non uniforme; quattro bin soddisfano i criteri, con le qualificazioni sopra. Non sono quattro componenti indipendenti.
3. **Identificabilità:** sufficiente operativamente sul picco entro M1 e l'intervallo dichiarato; non basta per attribuire fisicamente c o per certificare s come frequenza oceanica.
4. **Alternative:** sì, contaminante lento e rumore correlato senza offset possono favorire M1. Nessuna correzione giustificata.
5. **Prossimo esperimento proposto, non eseguito:** calibrare il guadagno predittivo con surrogati SAR-only sotto M0 e rumore temporalmente correlato, su picco fissato e un bin contrario (132,65), aggiungendo una partizione temporale alternativa prefissata. Stimare/scandire una gamma dichiarata di correlazioni dai residui senza adattarla per far vincere M1; i residui M0 possono contenere mismatch, quindi la calibrazione resta condizionata. Questo testa robustezza alla correlazione e alla partizione senza nuovi parametri nel modello reale o sottrazioni. Una nuova partizione non crea un record indipendente e da sola non distingue statico da lento.

**STOP — Block15D completato.** Evidenza predittiva compatibile con un offset nel modello adottato; origine fisica ancora non identificata. Risultati congelati e shortlist invariati.
