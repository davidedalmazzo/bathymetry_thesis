# Riordino funzionale del repository — 18 settembre 2026

Completamento degli spostamenti già preparati dall'utente, su conferma esplicita. La root Git `D:\Dati Tesi\Umbra` e il remote GitHub non cambiano. Struttura: [REPOSITORY_LAYOUT.md](../REPOSITORY_LAYOUT.md).

## Compatibilità

95 file di codice/test migrati nei percorsi letterali; 27 lettori di percorsi dinamici aggiornati con risoluzione esplicita. Le cifre si sovrappongono, non sono file distinti da sommare. Mappa `repository_paths.json`, resolver `code/repository_paths.py`; protezione traversal/URL/assoluti esterni. CLI FRF accetta percorsi operativi nativi e risolve input storici, incluso il percorso della cache legacy in configurazioni congelate senza riscriverle.

Guide operative e link README aggiornati. I vecchi checkpoint/report/manifest mantengono contenuti, nomi delle variabili, firme e percorsi originali: alcuni vecchi link/comandi vanno risolti mediante la mappa, non eseguiti alla cieca. I tre launcher `.bat` Umbra ora calcolano la root dalla loro posizione; formazione usa esclusivamente il venv di tesi. Nessuno di questi launcher è stato eseguito.

## Integrità e differenze

Baseline SHA-256 Block34: **810 hash verificati**, zero mismatch/non disponibili/irrisolti dopo risoluzione dei percorsi; include risultati/cache Block32/33 e checkpoint pertinenti. Il suo JSON originale resta intatto (`FROZEN_ARTIFACT_AUDIT.json`).

Audit dei 1266 spostamenti R100 pre-esistenti nell'indice: 1075 blob identici ai byte Git originali; 187 differiscono soltanto per la normalizzazione CRLF/LF che Git applicava già prima; quattro modifiche di contenuto autorizzate riguardano la guida FRF e i tre launcher. Questi stati NON equivalgono a nuovi mismatch della baseline congelata. `STAGED_MOVE_AUDIT.json` espone byte originali/attuali e classificazione, senza normalizzare i file per nascondere la differenza.

Manifest storici: Block32 delivery 184 verificati; Block33 123 verificati/10 mismatch; Block34 319 verificati/13 mismatch. I mismatch riguardano riferimenti a codice/documentazione/configurazione Git correnti cambiati rispetto alle versioni storiche, non riscritture dei risultati congelati. Dettagli/percorso originale/risolto in `HISTORICAL_MANIFEST_AUDIT.json`; non si aggiornano gli hash storici per farli coincidere con il nuovo codice.

## Verifiche operative

- Suite completa: **324 passed**, inclusi quattro nuovi test della mappa, invarianti numeriche e regressioni dei risultati. Comando/output in `FULL_SUITE.json`.
- Copia isolata FRF: **78 passed**, inclusi nei 324; cinque smoke singolo/ROI/batch/time-only/inventory-dry-run offline, cache mancante esplicita. Evidenze in `frf_delivery/`. Non clone GitHub e non installazione da zero.
- Batch reale dei tre input Block34 ricostruito dalla cache verificata copiata sotto `_cache/layout_frf`, output nuovo `outputs/layout_frf_cached`; **zero HTTP / zero byte nuovi** (`CLI_REAL_INPUT_OFFLINE.json`). Non sovrascrive i dossier congelati né i payload originali.
- `IGNORE_SAFETY.json`: esclusi nelle nuove posizioni cache, registry di rete, grandi intermedi, radar ed ambiente. `.gitattributes` preserva i byte dei nuovi percorsi degli artefatti.

Non sono stati spostati/ricreati gli ambienti, modificati prodotti originali, scaricati dati o svolti nuovi calcoli SAR/inversioni/dwell sweep. La collocazione fisica Umbra già avviata prima di questa task è stata mantenuta. Nessuna cancellazione, commit o push. Gli spostamenti già staged rimangono tali, le correzioni nuove restano locali.

Per ripetere soltanto audit e test senza rete:

```powershell
.\.venv-umbra-thesis\Scripts\python.exe scripts\verify_repository_layout.py --tests
```

`--delivery` aggiunge test isolati/smoke e un nuovo dossier offline, non download. Gli script `migrate_repository_paths.py` sono strumenti one-shot di migrazione, non parte dell'analisi scientifica ordinaria.
