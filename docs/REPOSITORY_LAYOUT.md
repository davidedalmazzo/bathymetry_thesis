# Struttura del repository della tesi

La root Git rimane `D:\Dati Tesi\Umbra`: il nome storico non indica che tutto il progetto dipenda da Umbra. Nessuna cartella sorella è creata fuori dal workspace.

| funzione | percorso attuale |
|---|---|
| scene Umbra e risultati Vandenberg | `umbra/Vandenberg/` |
| validazione Umbra/sintetica archiviata | `umbra/validazione/` |
| catalogo e selezione scene Umbra | `umbra/selezione_scene/` |
| preflight e mapping Samoa | `umbra/samoa/` |
| script dedicato Umbra | `umbra/scripts/` |
| Duck, CSK, TSX e osservazioni FRF | `duck_frf/Block30_…`–`Block34_…` |
| codice scientifico condiviso e client | `code/` |
| test ed esempi riutilizzabili | `tests/`, `examples/` |
| guide/checkpoint prima presenti in root | `docs/`, `docs/checkpoints/` |
| manutenzione e vecchi comandi Git | `scripts/`, `scripts/legacy_git/` |
| ambiente attivo | `.venv-umbra-thesis/` |
| cache/temporanei/output nuovi | `_cache/`, `_tmp/`, `outputs/` |

Gli ambienti non sono rinominati/spostati: un venv Windows non è garantito rilocabile. `.venv/` rimane storico, non è l'ambiente operativo. Nessun dato originale viene modificato. Il namespace Python `umbra_sar` rimane per compatibilità e non implica una scelta di sensore o metodo.

## Percorsi storici e hash

`repository_paths.json` è la mappa esplicita old→new. `code/repository_paths.py` risolve un percorso relativo o assoluto locale sotto la root; rifiuta URL, traversal ed assoluti esterni non autorizzati. Nessuna ricerca per basename né correzione automatica dei dati. I lettori di configurazioni/manifest usano la mappa al momento di aprire il file.

Gli artefatti congelati, inclusi manifest/checkpoint, NON sono riscritti. Alcuni link e comandi nei vecchi report continuano intenzionalmente a mostrare l'ubicazione storica: usare la mappa o aprire la nuova directory. I comandi operativi nelle guide correnti e i percorsi nel codice sono aggiornati. La verifica di codice storico può mostrare mismatch perché il codice è stato migrato; ciò è distinto dall'integrità dei payload/risultati. Non aggiornare i vecchi hash per nascondere queste differenze.

Audit del riordino e risultati dei test: `docs/reorganization/`. Le regole `.gitignore` escludono anche cache, radar e intermedi nelle posizioni nuove; `.gitattributes` conserva i byte degli artefatti. Non rigenerare vecchi output per aggiornare soltanto i percorsi.

## Uso

Eseguire sempre dalla root del repository:

```powershell
.\.venv-umbra-thesis\Scripts\python.exe -m pytest -q
.\.venv-umbra-thesis\Scripts\python.exe code\frf_client_cli.py --mode offline --acquisition-id prova --timestamp-utc 2021-10-12T11:07:16.616Z --output outputs\prova
```

Guida FRF: [FRF_QUICKSTART.md](FRF_QUICKSTART.md). Per input reali riusare, ad esempio, `duck_frf/Block34_frf_operational/ACQUISITIONS.json` e `CLIENT_CONFIG.json`, scegliendo un output nuovo. La guida precisa creazione/ripresa delle tranche; il riordino non autorizza alcuna nuova richiesta HTTP.

Nessun commit/push automatico durante questa migrazione. I movimenti Git già preparati dall'utente sono preservati; codice/docs nuovi sono modifiche locali finché non viene richiesto un altro push.
