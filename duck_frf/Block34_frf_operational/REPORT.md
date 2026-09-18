# Block34 — client Duck/FRF operativo v0.2.0

Consegna locale, 18 settembre 2026; nessun commit/push. Entrypoint stabile `code/frf_client_cli.py`, istruzioni PowerShell in `FRF_QUICKSTART.md`. Nuove acquisizioni si inseriscono tramite input/configurazione senza modificare il codice; assenze e fallimenti producono dossier parziali espliciti.

## Interfaccia e sicurezza

Singolo, footprint/ROI, batch, time-only, inventory/dry-run, fetch e offline. Configurazione, acquisizioni, budget e output separati. UTC, intervalli, geometrie lon/lat, collisioni ID e ROI esterne verificati prima della rete; nessuna ROI inventata o clipping implicito. Tranche nominate con creazione esplicita, ripresa persistente e rifiuto di reset/ampliamenti. Cache importate solo dopo SHA-256, senza vecchi budget. `representative_eligible` significa solo QC/tolleranza temporale implementati, NON rappresentatività fisica.

## Recupero realmente online

| evento originale | riferimento UTC richiesto |
|---|---|
| TSX-1 record 12 | 2021-10-12T11:07:16.616Z |
| COSMO 2098202 | 2021-10-13T22:45:03Z |
| TDX-1 record 11 | 2021-10-13T23:00:15.669Z |

Export/footprint/hash in `ACQUISITIONS.json` e `INPUT_PROVENANCE.json`. Il riferimento COSMO al secondo non è un centro fisico di apertura verificato; lo scarto dal timestamp originale frazionario è segnalato, non corretto.

Endpoint pubblico ufficiale FRF, TLS verificato, nessuna credenziale. Recuperati subset temporali di parametri/spettri e QC dei quattro strumenti ondosi (Waverider 17m/26m, AWAC 11m, 8m-array), profili di corrente, vento e livello. Dossier in `results/<evento>/`: REPORT, osservazioni, tensor, copertura, mappe e figure distinguono originali, derivati diagnostici, contesto, assenze e errori.

Survey 20211016, 20211008, 20211019: metadati verificati e subset del layout geografico 1D già supportato, primi 3000 indici per prodotto, conservati nell'unione dei footprint reali (`SURVEY_SUBSETS.json`). Quote originali NAVD88: nessuna conversione, copertura completa, contemporaneità per punto o inversione implicita. Survey 20211013: metadati falliti per timeout, nessun ulteriore retry senza nuove informazioni.

Tranche `block34_october_2021`: **25 transazioni / 3 253 569 byte**, limiti 50 HTTP / 100 MiB totali / 10 MiB per risposta. Retry e fallimenti contabilizzati. Registro persistente in `network/block34_october_2021/`, esportazione versionabile `NETWORK_AUDIT.json`. Nessuna necessità di consumare il residuo. **Consumo storico non determinabile**, non nullo né dichiarato conforme a vecchi limiti cumulativi.

## Confronto e limiti

`comparison/REPORT.md`, `EVENT_PARAMETERS.csv` e `SPECTRAL_DIAGNOSTICS.json` conservano parametri originali e diagnostiche native. COSMO/TDX condividono i record del 13 ottobre alle 23 UTC: non sono osservazioni indipendenti. WR17/AWAC: Hs circa 1.108/1.101 m, Tp pubblicati 9.547/8.316 s; massimi discreti 9.302/8.163 s. La differenza resta con la definizione comune di massimo nativo: nessuna attribuzione automatica a refrazione, corrente, strumento o sistemi distinti. Massimi numerici multipli non provano sistemi fisici; larghezza integrale non equivale alla larghezza del solo lobo. Griglie, definizioni e QC preservati, nessuna correzione direzionale.

8m-array: longitude della variabile +75.7428842, metadati nominali circa −75.7428906. Nessuna inversione automatica: entrambe le fonti conservate, posizione/distanze non valutabili, parametri ondosi invariati. Discrepanze minori degli altri strumenti restano incertezza nominale, non GPS verificato.

Microfrazioni CF conservate senza interpretarle come accuratezza strumentale; supporto/ancoraggio dei burst non sempre verificati. Vento non normalizzato a 10 m, correnti non equiparate alla superficie, QC ignoto distinto da respinto. Contesto non continuo fra eventi. Layout/protocolli non supportati restano espliciti; registro a singolo writer, nessuna garanzia concorrente.

## Consegna

320 test completi, 78 isolati già inclusi, cinque smoke offline; evidenze in JSON e `TEST_REPORT.md`. Copia isolata dei sorgenti dichiarati, senza cache privata/radar/credenziali: NON clone GitHub. Usa l'interprete prescritto esistente, non una nuova installazione pulita. Quindici confronti prima/dopo riuso cache numericamente/semanticamente identici, zero nuove richieste.

`FROZEN_AUDIT.json` distingue hash verificato, mismatch, non disponibile, percorso irrisolto; nessuna riscrittura dei manifest storici. `MANIFEST.json` ha SHA-256 e percorsi relativi. `FILES_TO_VERSION.json` elenca esattamente sorgenti/test/fixture/esempi/docs necessari e stati tracked/modified/new/ignored; aggiungere gli artefatti versionabili Block34 e i documenti indicati. Cache, registro grezzo e copie isolate esclusi; audit JSON esportato senza segreti. Codice aggiornato con provenienza corrente, dati congelati preservati. Nessuna lettura/formazione radar, inversione, dwell sweep o scelta di scena. Arresto CHECKPOINT_34.
