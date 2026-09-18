# CHECKPOINT_34 — client Duck/FRF operativo

Client v0.2.0 consegnato localmente, nessun commit/push. Entrypoint `code/frf_client_cli.py`, `FRF_QUICKSTART.md`, relazione `Block34_frf_operational/REPORT.md`.

Input mission-neutral, validazione prima della rete, config/budget separati, tranche nominate persistenti, cache SHA-256 verificata. Tre eventi originali TSX 12/COSMO 2098202/TDX 11 con dossier e confronto; nessuna ROI inventata o scelta definitiva di scena.

Live: 25 transazioni / 3 253 569 byte; nuova tranche 50 HTTP / 100 MiB / 10 MiB per risposta. Consumo storico non determinabile. Parzialità: survey 20211013 timeout, posizione 8m-array irrisolta per conflitto longitude senza correzione automatica. Tre survey con subset limitati NAVD88, nessuna inversione.

320 test completi, 78 isolati già inclusi, cinque smoke offline. Quindici confronti numerico-semantici uguali dopo riuso cache, zero HTTP. Hash congelati e manifest correnti con stati espliciti. Copia isolata locale senza cache/radar/credenziali, NON clone GitHub; ambiente esistente, nessuna installazione pulita dichiarata.

`FILES_TO_VERSION.json` indica sorgenti/docs/test/fixture/esempi necessari e stati Git; cache/registro grezzo/copie isolate esclusi, audit del registro esportato in JSON. Nessuna lettura/formazione radar, inversione, dwell sweep, modifica risultati congelati o push. Arresto alla consegna.
