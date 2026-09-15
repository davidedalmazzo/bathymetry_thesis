# Block18 — protocollo congelato per il recupero spettrale per-bin

## Identificatore e stato iniziale

`Block18` è il primo identificatore libero: Block16A, Block16B/Checkpoint16 e
Block17 esistono; non risultavano artefatti Block18 all'avvio.

- Commit iniziale: `6ab3318084098440eb030a4859f8d19fc9455d8c`.
- Worktree iniziale: modifiche Block17/WORKLOG non ancora committate e output
  Block16/Block15 già presenti e non tracciati. Sono preservati.
- Interprete esclusivo: `.venv-umbra-thesis/Scripts/python.exe`.
- Configurazione finale congelata prima della rete: SHA-256
  `deccd38faec8c7f2d0ef1f42a3d3a768fa76676da7c8237ffd441bf3ec2d406e`.
  Una prima bozza (`06c3…c698`) è stata sostituita prima di ogni richiesta per
  includere esplicitamente il template degli URL storici; nessun dato era stato
  ancora recuperato o esaminato.

## Popolazione congelata

Le quattro acquisizioni sono derivate programmaticamente da
`BLOCK16A_MEASURED_SPECTRA.csv`, senza selezione per esito. Sono elencate nella
configurazione con collect, data, stazione 42084, distanza, osservazione, URL e
hash storici.

## Politica congelata prima delle richieste

1. Cercare bytes locali con l'hash storico; poi verificare timestamp e
   coordinate dell'aggregato corrente; quindi subset aggregato, archivio
   annuale e infine CDIP solo con deployment verificabile.
2. Non fidarsi dell'indice storico: scegliere l'indice corrente dal vettore
   `time` e verificare il timestamp restituito.
3. Scoprire forma e coordinate tramite metadata DDS/DAS; nessuna ipotesi di 98
   bande.
4. Separare bytes grezzi e normalizzazione. Missing per variabile derivati
   dagli attributi `_FillValue`/`missing_value`; 99 gradi non è genericamente
   missing.
5. Tolleranze ereditate: distanza ≤50 km, |offset| ≤3600 s; ordinamento
   `(distance_km, station_id, source_priority)`.
6. Block17 non congelava la banda nel JSON, ma la funzione versionata usa
   `[0.04, 0.25] Hz`: questa è congelata qui prima dei payload. Si riportano
   inoltre coperture sull'intervallo prodotto e `f ≤ 0.1 Hz`. Soglia congiunta
   ereditata: almeno 0.90 dell'energia valida nella banda.
7. Un riferimento ammissibile non implica rappresentatività idrodinamica né
   promozione automatica. Nessun MEM o conteggio di sistemi.

## Budget applicato durante lo streaming

- massimo 100 transazioni HTTP complessive, redirect e retry inclusi;
- massimo 50 MiB complessivi e 10 MiB per risposta;
- timeout 45 s; massimo 2 retry;
- ogni risposta viene letta a chunk e interrotta prima di superare il limite;
- subset lato server; nessun archivio annuale completo;
- stop esplicito su budget, risposta non subset o requisito fuori ambito.

## Invarianti e arresto

Nessun prodotto SAR, pixel SICD, signal CPHD, Vandenberg, nuovo catalog crawl,
formazione, dwell sweep, inversione, commit o push. I blocchi precedenti non
sono sovrascritti. Il blocco termina dopo payload/normalizzazione, confronto
metriche, rivalutazione delle sole quattro scene, test offline e manifest.
