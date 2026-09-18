# Block15G — separabilità sintetica di due componenti

## Esito

Questo è un esperimento sintetico di coefficienti Fourier dell'intensità, non un fit Q2 a Vandenberg. Con 96 realizzazioni complete (36 calibrazione, 60 valutazione), Q2 distingue e recupera entrambe le componenti quando separazione spaziale e temporale sono sufficienti; può invece essere selezionato senza recuperare le frequenze nei casi sovrapposti. I controlli a una componente e offset non hanno falsi Q2 con il gate calibrato.

## Disegno e limiti

Protocollo/configurazione definiscono tempi BP12, finestra Tukey effettiva, patch e semi. La risposta spaziale è la DFT esatta della finestra BP12 288×130, non un lobo gaussiano scelto. Il rumore proprio complesso usa covarianza spaziale della finestra-quadrata e OU temporale ai tempi irregolari (`tau=0` o `5 s`). Non sono costruiti vicini identici per alzare MSC; bin e fold non sono repliche indipendenti.

Q0 è una componente, Q1 una componente+offset statico, Q2 due componenti. Tutti usano variable projection globale su [-1,+1] rad/s e lo stesso peso. La selezione è fatta esclusivamente con 8×4 purged (due look guard), rifittando sul training; la 4×8 Block15D è registrata come controllo secondario. La soglia, congelata come `max(0.10,q95 calibrazione)`, è risultata 0.10. Le componenti Q2 possono scambiarsi etichetta; recupero richiede entrambe entro `min(.03, .25 Delta_s)`.

Il trasferimento geometrico tilt+Jacobiano Block15F è calcolato separatamente per ogni k. Il fit “geometry-informed” riceve H sintetico noto: è un controllo favorevole, non capacità dimostrata su dati reali. Il termine idrodinamico X-band resta assente.

## Risultati finali

| Caso, 12 repliche | Q2 selezionato costante/geom | entrambe recuperate costante/geom | selezionato ma non recuperato costante/geom |
|---|---:|---:|---:|
| Stress non risolto, Delta_s*Tobs≈0.50, Delta k=.25 bin | 12/12, 0/12 | 0/12, 0/12 | 12/12, 0/12 |
| Stress temporale, Delta_s*Tobs≈3.01, Delta k=3 bin | 12/12, 12/12 | 12/12, 12/12 | 0/12, 0/12 |
| Fisico overlap, h=10 m, Delta k=1 bin, tau=5 s | 9/12, 12/12 | 0/12, 0/12 | 9/12, 12/12 |
| Fisico separabile, h=10 m, Delta k=6 bin | 12/12, 12/12 | 12/12, 12/12 | 0/12, 0/12 |
| Fisico debole, ratio=.3, Delta k=6 bin, tau=5 s | 7/12, 8/12 | 8/12, 10/12 | 0/12, 0/12 |

I guadagni medi Q2 purged sono circa .20/.15 nel caso stress non risolto, .48/.50 nel fisico overlap, .51/.52 nel fisico separabile, .16/.16 nel debole persistente e .52/.53 nello stress temporale (costante/geometry). La 4×8 secondaria dà medie quasi uguali: rispettivamente .20/.15, .48/.49, .51/.52, .16/.16 e .52/.53. Non è una nuova prova di indipendenza, ma il pattern non è artefatto esclusivo dello split purged.

Controlli di calibrazione: 0/12 Q2 selezionati per componente singola costante, 0/12 per singola con trasferimento geometrico, 0/12 per offset statico, con entrambi i fit di trasferimento. Questi sono falsi positivi empirici zero su 72 fit modello/controllo, non una garanzia o un limite statistico universale. Il rumore persistente da solo non ha favorito Q2 in questa scala/SNR, mentre l’overlap fisico lo favorisce senza recupero: rilevamento e recupero sono metriche diverse.

## Interpretazione

Due componenti sono recuperabili qui quando hanno lobi distinti nella risposta della finestra e separazione temporale dell’ordine di alcune unità su `Delta_s*Tobs`; la scala 1/Tobs non è un confine assoluto, ma il caso 0.50 è non identificabile. Il caso fisico con un solo bin di separazione è il risultato più istruttivo: Q2 migliora la predizione ma non risolve le frequenze. Non si deve quindi usare la sola selezione Q2 come prova di due onde.

Il trasferimento noto cambia poco i casi chiaramente separabili e può cambiare la selezione in casi limite; non elimina l’overlap. Ciò è coerente con Block15F: la fase geometrica è piccola e non un correttore di frequenza. Nessuna conclusione su Vandenberg è consentita.

Prima di applicare Q2 a qualunque dato reale servirebbero: due lobi/spatial templates risolti sul supporto osservato, guadagno predittivo purged, recupero stabile rispetto a transfer plausibili, assenza di minimi fusi/ampi e controllo su lobo coniugato. In particolare, l’offset M1 e rumore correlato dei Block15D/E restano spiegazioni concorrenti.

Test coprono risposta/leakage della finestra, recupero noiseless, simmetria di etichetta, seme/covarianza, guard/train/test e degenerazione. Figure mostrano selezione/recupero e guadagno contro separazione; i costi globali e i loro conteggi di minimi restano nei record Q2 per ogni realizzazione. Nessun dato radar o risultato congelato è stato modificato.

Prossimo unico esperimento: una piccola serie sintetica con **offset statico più due componenti parzialmente sovrapposte**, mantenendo i gate congelati, per misurare esplicitamente la confusione Q1/Q2 prima di qualsiasi fit reale.

**STOP — Block15G completato.**
