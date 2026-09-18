# Block15K — chiusura causale e dominio di applicabilità per Vandenberg

## Esito

Il gap storico fra SICD e BP12 si chiude **numericamente** dopo il matching: sul medesimo rettangolo oceanico 1440×650 m, sul medesimo coefficiente fisico e con tre kernel temporali quasi coincidenti, le pendenze sono `−0.4034622` e `−0.4036850 rad/s`. Il residuo è `0.0002228 rad/s` (0.055% rispetto al SICD appaiato). Questo è molto inferiore alla tolleranza prefissata, ma non costituisce un’attribuzione causale completa: i tre look forniscono un fit a un solo grado di libertà e la pesatura SVA/PFA pixel-dipendente del SICD non è disponibile. Vandenberg viene quindi congelato come **development/stress test**, non come scena di validazione fisica.

Non è stata calcolata alcuna frequenza, periodo o profondità “corretta”. I valori storici restano immutati.

## Riproduzione e convenzioni

Gli artefatti congelati riproducono esattamente la pendenza SICD `−0.3509722055 rad/s`. Per BP12 il JSON storico riportava il modulo `0.4120656492 rad/s` al bin negativo `(133,65)`; la mappa salvata mostra `+0.4120656492` a quel bin e `−0.4120656492` al coniugato positivo `(155,65)`. Il confronto usa quest’ultimo, coerente con il vettore geografico canonico positivo SICD. L’errore di riproduzione del modulo e del segno dopo questa trasformazione esplicita è zero; le somme delle pendenze sui lobi coniugati sono zero alla precisione numerica.

La convenzione è sempre `F_secondary * conj(F_reference)`. Si tratta della fase dei coefficienti Fourier delle immagini di **intensità**, non della fase radar.

## Audit dei percorsi

La tabella completa è in `BLOCK15K_PATH_AUDIT.csv`. Gli elementi principali sono:

| Quantità | SICD | CPHD/BP12 | Stato |
|---|---|---|---|
| tempo disponibile | apertura processata 18.068061721 s | slow time 22.540812513 s | distinti |
| formazione | PFA del fornitore, SVA senza `WgtFunct` | backprojection documentata, 165924 impulsi | non equivalenti |
| look finali | 3 sub-bande ~5.8 s, Tukey 0.25 esplicita sopra SVA ignota | 32 box da 0.7044 s ricombinati coerentemente | parzialmente appaiati |
| centri | 3.2429, 9.0365, 14.8323 s | 3.2335, 9.0383, 14.8421 s | errore massimo ~0.010 s |
| kernel | Tukey continuo PVP-mapped | proiezione sulla base BP12 | cosine 0.985–0.992 |
| ROI/griglia | SICD resampled sul rettangolo Block7 | griglia BP 288×130, 5 m | appaiati |
| analisi spaziale | piano globale + Tukey 0.1 + FFT non padded | identica | appaiata |
| coefficiente | +k fisico congelato | stesso +k, non massimo temporale | errore 0.0001126 rad/m |
| terra | controllo Block4 congelato | nessuna BP terrestre esistente | controllo non appaiato |

L’errore sul vettore d’onda è 0.0258 bin nativi, cioè 0.0116 `delta_eff`. I kernel rispettano tutte le tolleranze congelate: errore dei centroidi della proiezione BP ≤1.60 ms, differenza di durata RMS ≤30.3 ms e similarità coseno ≥0.9847. Rispetto ai centri PVP attribuiti ai look SICD, la discrepanza massima resta circa 10 ms.

## Scala di ablation

I gradini condividono la medesima acquisizione e non sono repliche indipendenti. Le variazioni non sono additive e le percentuali non sono una decomposizione causale.

| Gradino | SICD [rad/s] | BP [rad/s] | differenza | differenza/SICD |
|---|---:|---:|---:|---:|
| A — storici congelati | −0.350972 | −0.412066 | 0.061093 | 17.41% |
| B — supporto temporale comune | −0.350972 | −0.407299 | 0.056326 | 16.05% |
| C — ROI/griglia/finestra/patch comuni | −0.403462 | −0.400484 | 0.002978 | 0.738% |
| D — tre look kernel-matched | −0.403462 | −0.403685 | 0.000223 | 0.055% |
| E — residuo di formazione | −0.403462 | −0.403685 | 0.000223 | 0.055% |

Il solo vincolo temporale spiega numericamente `0.00477 rad/s`, circa il 7.8% del gap storico. Il passaggio C riduce gran parte del resto, ma modifica congiuntamente supporto spaziale, griglia, patch e campionamento temporale SICD; non è lecito assegnare quella riduzione a uno solo di questi fattori. Il matching dei look riduce ulteriormente il residuo di `0.00276 rad/s`. Complessivamente il residuo osservato diminuisce del 99.64%, ma questa percentuale descrive la chiusura numerica della sequenza di processing, non una quota causale identificata.

Nel confronto finale: SICD `R²=0.9953`, RMSE `0.1310 rad`, MSC adiacente minima `0.884`; BP `R²=0.9849`, RMSE `0.2367 rad`, MSC minima `0.836`. I periodi puramente derivati dai fit appaiati sono 15.573 e 15.565 s e sono riportati solo come metrica del confronto, non come nuovi periodi fisici. Il massimo passo fra i tre look è 2.845 rad: non supera π, ma fallisce il più conservativo gate `<π/2`. Il controllo terrestre congelato resta non risolto (`+0.00605±0.01696 rad/s`, `R²=0.0193`) e non mostra una rampa comune; non esiste però una backprojection terrestre appaiata.

## Attribuzione delle differenze

1. **Supporto temporale:** effetto quantificato, piccolo rispetto al gap iniziale.
2. **ROI, griglia, finestra e selezione del coefficiente:** effetto congiunto numericamente grande, ma non separabile perché interagisce con il cambiamento da 11 look SICD storici ai tre look allargati.
3. **Durata, forma e centri dei look:** proiezione BP ben appaiata e riduzione osservabile del residuo; la componente SVA nativa resta ignota.
4. **Formazione:** il residuo finale è numericamente trascurabile rispetto alla tolleranza `0.1142 rad/s`, dominata dall’incertezza dei fit a tre punti. Non è evidenza di equivalenza degli operatori.
5. **Causalità:** non identificabile in senso stretto. Non è possibile distinguere completamente supporto spaziale, composizione del lobo e formazione del fornitore con una sola acquisizione e tre look comuni.

## Dominio di applicabilità

### Livello 1 — rilevamento cinematico

**Supportato con limitazioni.** Le serie indipendenti storiche a 11 e 32 look mostrano segno coerente, fit regolari e dipendenza debole dal baseline; il controllo terrestre non mostra la stessa rampa. Il test finale a tre look riproduce la pendenza fra i percorsi, ma fallisce il gate conservativo sul passo `<π/2` e ha incertezza ampia. Il criterio generale richiede almeno mezzo ciclo osservato, `R²≥0.97`, MSC patch ≥0.5, continuità di fase, lobo/segno verificati e nessuna riselezione temporale del picco.

### Livello 2 — interpretazione come frequenza ondosa

**Non identificabile.** Il vicino è a 1.35 FWHM/`delta_eff`, sotto il requisito provvisorio di 2; i bin vicini non sono componenti indipendenti; Block15I non discrimina le famiglie e Block15J non rileva i contributi OU-lenti. Anche la robustezza fra supporti storici e comuni è insufficiente per attribuire una singola frequenza fisica. La boa non seleziona quale pendenza SAR sia “corretta”.

### Livello 3 — inversione batimetrica

**Non supportato; astensione obbligatoria.** Il Livello 2 fallisce, il lobo possiede soltanto 2.014 elementi radiali effettivi contro i quattro richiesti, `ω(k)` non è risolta in modo indipendente e rimane la degenerazione profondità–corrente–imaging.

Le soglie di separabilità e stabilità sono requisiti provvisori da calibrare su scene di validazione; non sono proposte come soglie universali.

## Classificazione finale di Vandenberg

| Aspetto | Classificazione |
|---|---|
| formazione e convenzioni | supportato con limitazioni |
| rilevamento cinematico | supportato con limitazioni |
| stabilità della pendenza | supportato con limitazioni |
| singola componente | non identificabile |
| confronto con boa | non identificabile |
| interpretazione dispersiva | non identificabile |
| inversione della profondità | non supportato |

Verdetto complessivo: **utilizzabile soltanto come stress test di sviluppo**. Sono robusti il segno numerico, la simmetria coniugata, la presenza di una fase temporale regolare, la scala spaziale centrale ~130 m e la concordanza dei percorsi quando supporto e look vengono appaiati. Restano non identificabili la causa esatta del gap storico, il contenuto fisico del vicino spettrale, una frequenza oceanica unica e la profondità.

## Risposte richieste

1. I fattori controllabili chiudono numericamente il 99.64% del gap, ma soltanto il 7.8% è isolato come puro effetto del supporto temporale; il resto è un effetto interagente non causalmente scomponibile.
2. Non rimane una sensibilità numerica significativa nel confronto finale, ma la sensibilità alla formazione non è esclusa con precisione utile.
3. No: i percorsi sono parzialmente appaiati, non causalmente equivalenti, per SVA/PFA ignota e tre soli look comuni.
4. Sì, rilevamento cinematico supportato con limitazioni sulla base delle serie storiche più lunghe.
5. No: frequenza ondosa singola non identificabile.
6. No: inversione batimetrica non supportata, con astensione.
7. Segno, lobo coniugato, fase regolare, scala spaziale centrale e concordanza appaiata sono robusti.
8. Causa del gap storico, componente singola, trasferimento lento, frequenza oceanica e profondità restano non identificabili.

Vandenberg è congelato al termine di questo blocco.

## Chiusura della provenienza

Il manifest Block15K registra hash espliciti per gli artefatti essenziali 15I, 15J e 15K. Il limite storico resta dichiarato: Block15I riportò i 107 test ereditati da Block15H e non aveva un modulo pytest dedicato. Block15J aggiunse 10 test mirati (117 totali); Block15K ne aggiunge 18. Nel ricontrollo del manifest 15J, tutti gli artefatti immutabili coincidono; cambia soltanto l’hash di `WORKLOG.md`, come previsto per l’append cronologico del Block15K. Nessun artefatto congelato 15I/J è stato riscritto.
