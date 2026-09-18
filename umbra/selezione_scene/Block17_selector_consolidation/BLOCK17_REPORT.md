# CHECKPOINT 17 — consolidamento del selettore Umbra

## Esito

Il baseline Block16A è stato riprodotto offline esattamente: **A 0, B 1, C 33, D 10106, E 0**. Nessuna scena cambia categoria, perché le correzioni semantiche sono certe ma gli array spettrali per-bin necessari a rivalutare i quattro riferimenti misurati non sono archiviati. Applicare una riclassificazione sarebbe inventare evidenza.

Non sono state effettuate richieste di rete, letture SAR, nuove estrazioni di coefficienti o modifiche ai risultati Vandenberg/Blocks 15–16.

## Difetti verificati

Sono confermati: arresto storico al primo payload spettrale recuperato; priorità potenziale a uno spettro fuori finestra; test `any finite` anziché validità congiunta; query rigida a 98 bin; solo archivio `w9999`; integrazione trapezoidale capace di collegare missing; massimo-locale chiamato sistema; conteggio nominale chiamato indipendente; CPHD e SICD fusi in `usable_duration`; proxy geometrico sovrainterpretato. È invece falso che mancasse il filtro marino 80%.

La libreria `selector_consolidation.py` corregge le primitive senza alterare il codice storico necessario alla riproducibilità.

## Impatto sulle categorie

La tabella completa conserva per ogni acquisizione categoria precedente/corretta, causa e stato di riaudit. Le 4 scene con riferimento misurato sono marcate `not_reproducible_from_archived_summary_missing_per_bin_joint_mask`. Il caso long-dwell di 43.186 s resta C: durata eccellente, ma nessuna promozione fondata sui nuovi criteri.

Il controfattuale identifica 842 righe sotto l'80% marino che superano area e clearance legacy. Non sono candidate promosse: la clearance di un solo punto non dimostra l'esistenza di una ROI orientata e omogenea.

## Audit della larghezza sintetica

Con `f0=0.08377 Hz`, 256 componenti e 400 realizzazioni:

| ε | σ target (Hz) | corretto/target | legacy/target |
|---:|---:|---:|---:|
| 0.03 | 0.0025131 | 0.9962 | 0.7079 |
| 0.08 | 0.0067016 | 1.0002 | 0.7062 |
| 0.177 | 0.0148273 | 0.9996 | 0.7066 |

Il test discrimina quantitativamente il difetto: il legacy realizza `σ/√2`, il generatore corretto realizza la larghezza dichiarata. Per ε=0 entrambi degenerano correttamente in una singola frequenza.

Il CSV/JSON registra anche distribuzione Monte Carlo del centro energetico, bias rispetto a `f0`, rifiuti e degenerazioni. Il centro è una statistica dichiarata della distribuzione, non una “frequenza vera unica” del sistema distribuito.

## Criteri esplorativi

Restano descrittivi, non gate: precisione off-grid oltre la spaziatura FFT in condizioni parametriche; curve `ω(k,h)` su banda finita; velocità di gruppo; propagazione completa con covarianza; supporto ROI proiettato lungo la propagazione. Nessuno di questi valori è stato usato per migliorare il ranking.

## Artefatti e limite riproducibile

- `BLOCK17_BASELINE_CORRECTED.csv`: 10.140 acquisizioni, zero cambi categoria.
- `BLOCK17_REVISED_SHORTLIST.csv`: 34 righe A/B/C con nomi semantici corretti.
- `BLOCK17_SYNTHETIC_WIDTH_AUDIT.{csv,json}` e `BLOCK17_THEORY_CHECKS.json`.
- `BLOCK17_ERRATA.md` e `BLOCK17_THEORY_ASSUMPTIONS.md` documentano cosa resta valido.

Il prossimo passo unico raccomandato è un recupero metadata-only, strettamente budgettato, dei payload spettrali per-bin delle sole quattro acquisizioni già misurate, salvando frequenze, larghezze, missing mask e cinque campi direzionali. Solo allora il criterio congiunto può legittimamente cambiare una categoria.
