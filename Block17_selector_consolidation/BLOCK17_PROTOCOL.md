# Block17 — protocollo congelato di consolidamento del selettore

Identificatore scelto: **Block17**. `Block16A` identifica il selettore,
`BLOCK16B_WIDTH_CRITERION` e `CHECKPOINT_16` esistono già; non risultano file
Block17 nel repository all'avvio.

## Stato iniziale

- Commit: `6ab3318084098440eb030a4859f8d19fc9455d8c` (`main`, allineato a
  `origin/main`).
- Modifiche preesistenti: soltanto output numerici/cache non tracciati già
  esclusi dal push precedente; nessun file tracciato modificato.
- Interprete obbligatorio: `.venv-umbra-thesis/Scripts/python.exe`.

## Interventi congelati

1. Versionare primitive corrette per riferimenti, bande, tempi, ROI e teoria,
   senza riscrivere Block16A.
2. Separare spettro recuperato, valido nel tempo, con copertura congiunta,
   utilizzabile per screening e indipendente.
3. Provare tutte le stazioni ammesse in ordine `(distanza, station_id)` e
   distinguere esiti di archivio/rete/parsing.
4. Integrare per larghezze di banda quando disponibili, senza colmare missing.
5. Rinominare massimi locali, look nominali e clearance geometrica secondo ciò
   che misurano realmente.
6. Conservare la baseline marina `ocean_fraction >= 0.80`; quantificare a parte
   il controfattuale ROI-interna senza promozione.
7. Conservare `band_trial_legacy` e confrontarlo con un generatore avente
   densità energetica target esplicita sui tempi irregolari BP12 archiviati.
8. Verificare derivate/propagazione con covarianza e controlli off-grid e
   dispersion-consistent; nessuna soglia esplorativa diventa un gate.
9. Riprodurre Block16A esclusivamente dagli artefatti dello snapshot
   `20260913T231747Z`; nessun nuovo crawl.

## Budget e arresto

- Query remote pianificate: **0**; massimo eccezionale: 10 richieste/5 MiB,
  solo se un controllo non è risolvibile dalla cache.
- Seed sintetico: `17001`; massimo 400 realizzazioni per configurazione.
- Vietati radar pixels, CPHD signal, nuovi coefficienti reali, formazione,
  dwell sweep, inversione, correzione di pendenze e download SAR completi.
- Se la completezza spettrale storica non è ricostruibile dai file archiviati,
  il risultato resta `not_reproducible_from_archived_summary`; non si interroga
  la rete per trasformarlo in assenza di riferimento.
- Block15G–K, Block16A e la classificazione Vandenberg restano immutabili.

## Criteri di esito

Una categoria cambia solo per una correzione dimostrata con dato archiviato.
Le sensibilità ROI/larghezza/gradiente sono descrittive e non promuovono scene.
Il blocco termina con test offline completi, errata, confronto baseline/corretto,
summary e manifest hashato, anche se non emerge alcuna scena A.
