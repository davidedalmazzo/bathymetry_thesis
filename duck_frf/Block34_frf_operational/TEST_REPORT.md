# Verifiche Block34

- Suite completa: 320 passed (`FULL_SUITE.json`), interprete locale prescritto.
- Copia isolata: 78 passed (`ISOLATED_TESTS.json`), inclusi nei 320, NON 398 casi distinti.
- Cinque smoke: singolo, ROI, batch, time-only, inventory/dry-run. Exit 0, cache assente esplicita, zero HTTP (`CLI_SMOKE.json`).
- Mock locali: tranche create/resume/no-reset/no-ampliamento; path sicuri; cache verificata gratuita/corruzione esclusa; validazione prima della rete; ROI esterna esplicita; longitude conflittuale non corretta; QC mancante distinto da respinto.
- Quindici confronti numerico-semantici identici dei tre dossier dopo riuso offline (`CACHE_REUSE_COMPARISON.json`), zero nuove richieste.
- Hash congelati Block32/33 e checkpoint pertinenti: `FROZEN_AUDIT.json`, quattro stati espliciti, nessuna modifica dei manifest precedenti.
- Live separato: 25 transazioni / 3 253 569 byte. Installazione da zero non eseguita, dipendenze già presenti. Copia isolata locale NON clone GitHub.

Gli output JSON sono evidenza dei comandi/esiti; non sommare ripetizioni o test isolati alla suite come casi nuovi.
