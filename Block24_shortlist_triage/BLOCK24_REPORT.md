# Block 24 — chiusura del preflight candidato 2 e triage dell'intera shortlist

Data: 2026-09-15. **Nessuna rete, nessun dato SAR letto, nessun download
raccomandato.** Tutto da artefatti congelati: Block16A marine geometry,
Block21 shortlist e reference bins, Block22 e Block23.

## 1. Candidato 2: il Block23 era completo, non interrotto

Il Block23 ha raggiunto una decisione — **NON_PRIORITY** — ed è corretta. SICD e
CPHD sono dichiarati nello STAC ma puntano al bucket privato
`s3://prod-prod-processed-sar-data/...` e danno **404** su ogni nome pubblico
provato (6 richieste, 11 982 byte).

**Quello che mancava è il perché, e si vede offline.** Nella
`BLOCK21_SHORTLIST.csv` il candidato 2 è **l'unico** con *entrambe*
`sicd_size_bytes` e `cphd_size_bytes` vuote:

| # | sicd_size_bytes | cphd_size_bytes |
|---|---|---|
| 1 | 13 799 853 988 | — |
| **2** | **(vuoto)** | **(vuoto)** |
| 3 | 25 044 149 055 | — |
| 4 | 248 448 406 | 4 252 671 232 |
| 5 | 490 711 759 | — |

Il crawler Block16A legge il **listing pubblico** di S3: una dimensione nulla
significa che l'oggetto non è mai stato visto lì. **`has_sicd`/`has_cphd`
vengono invece dalla dichiarazione STAC.** Il Block21 ha gattato sul flag
sbagliato. Correzione al selettore: usare la presenza di `*_size_bytes`, non i
flag `has_*`. Sarebbe costato zero richieste.

## 2. Triage degli altri candidati, in un colpo solo

Invece di un preflight per volta, cinque discriminanti calcolabili offline.
Convenzione dell'asse range verificata: riproduce **67.17°** del Block22
(candidato 1) e **71.82°** del Block23 (candidato 2).

| # | complesso pubblico | Δ assiale | δL/L | λ nella ROI | Δφ | Hm0 | T | cut-off |
|---|---|---|---|---|---|---|---|---|
| 1 | sì, SICD 13.8 GB | 67.2° | 0.246 | 4.1 | 116° | 0.82 m | 15.38 s | ok |
| 2 | **NO** | 71.8° | 0.369 | 2.7 | 228° | 0.58 m | 15.38 s | ok |
| 3 | sì, SICD 25.0 GB | 51.0° | 0.185 | 5.4 | 235° | 0.75 m | 13.33 s | ok |
| **4** | sì, SICD 248 MB + CPHD 4.25 GB | **9.4°** | **0.024** | **42.4** | 138° | **0.26 m** | 4.76 s | ok |
| 5 | sì, SICD 491 MB | **89.0°** | 0.319 | 3.1 | 147° | 0.94 m | 14.29 s | ok |

### Cosa dicono

**Il criterio di fase lo passano tutti** (Δφ = 116–235°, banda buona 45–300°),
**incluso il candidato 4 con 2.8 s di dwell**. Conferma che la durata non è il
discriminante.

**Il cut-off azimutale non morde per nessuno**: λ_c stimato 23–40 m contro onde
da 35 a 369 m. Non è quello il problema.

**Discrimina la geometria.** Il candidato 5 sta a **89.0°**: onda che viaggia in
azimut puro, il caso peggiore possibile. Il 3 a 51°, l'1 a 67°, il 2 a 72°.
Solo il **candidato 4 è allineato al range (9.4°)**.

**E discrimina la risoluzione in numero d'onda.** I candidati 1, 2, 3, 5 hanno
**2.7–5.4 lunghezze d'onda dentro la ROI**, quindi `δL/L = 0.185–0.369`. È
esattamente la condizione che ha prodotto il taglio a `L > 200 m` di Romeiser
(finestra 1024 m, ~5 lunghezze d'onda, ~20%). Il candidato 4 ne ha **42**, con
`δL/L = 0.024`: un ordine di grandezza meglio.

## 3. Il gate che manca al Block21: l'energia del mare

**Tutti e cinque gli stati di mare sono deboli.** `Hm0` ricalcolato dai bin:
**0.26 – 0.94 m**. Vandenberg aveva **1.99 m**, cioè da 2.1× a 7.6× di più — e
lì il Livello 2 era già `non identificabile`.

Il Block21 gatta su `joint_energy_coverage`, che vale 1.0 per tutti e cinque: ma
quella misura la **completezza direzionale del record della boa**, non l'energia
del mare. Sono due cose diverse e il selettore le confonde.

Il candidato 4, il migliore su geometria e risoluzione, ha **Hm0 = 0.26 m** con
`L = 35 m`: ripidità `H/L = 0.007`. Mare quasi piatto. La modulazione di tilt e
idrodinamica sarebbe al livello dello speckle.

## 4. Nota sul candidato 4

Poligono STAC centrato a **36.995 N, −76.152 W**: imboccatura della Chesapeake
Bay / Hampton Roads, Virginia. GEBCO sul footprint: **−7, −8, −8, −10, −16 m**.
Con `L = 35.4 m` serve `h > 17.7 m` per l'acqua profonda: siamo in acqua
**intermedia**, `kh ≈ 1.6`, `tanh ≈ 0.93` — abbastanza vicino da rendere la
predizione poco sensibile alla profondità, ma non priva di parametri.

Due riserve ulteriori: l'offset dalla boa è **+1752 s (29 min)**, il maggiore
della shortlist, e un mare di vento a 4.76 s evolve in mezz'ora; e la Chesapeake
ha correnti di marea di 1–1.5 m/s, che a `k = 0.18 rad/m` valgono `kU ≈ 0.18`
contro `σ = 1.32`, cioè un termine Doppler del 13%.

`maximum_sliding_center_count = 2` **non è un limite reale**: viene dalle durate
nominali Block21 (1.5–6 s), dimensionate per onde da 15 s. Per un'onda da 4.76 s
sono appropriati look da ~0.7 s, che su 2.8 s danno 4 look disgiunti o ~11
scorrevoli a passo 0.2 s. La tabella temporale del Block21 sotto-serve il caso a
periodo corto.

## 5. Decisione

**Nessuno dei cinque è conforme**, e i motivi sono ordinati:

- **candidato 2** — nessun prodotto complesso pubblico. Chiuso dal Block23.
- **candidato 5** — Δ assiale 89.0°, onda in azimut puro. Chiuso.
- **candidato 3** — Δ assiale 51.0°, `δL/L = 0.185`, 25 GB per il solo SICD,
  nessun CPHD. Non prioritario.
- **candidato 1** — Δ assiale 67.2°, `δL/L = 0.246`, 13.8 GB, nessun CPHD.
  Non prioritario.
- **candidato 4** — l'unico con geometria e risoluzione adeguate e con
  **entrambi** i prodotti a costo basso (4.5 GB in tutto), ma `Hm0 = 0.26 m`.
  **Condizionato**: sarebbe il primo download se esistesse un'acquisizione
  equivalente con mare più energico.

La causa comune non è un difetto dei candidati: è che **il selettore non ha un
gate sull'energia del mare né sull'allineamento onda-range**, e ordina
principalmente su prossimità della boa e dimensione della ROI.

## 6. Il passo successivo, uno solo

Rieseguire il selettore Block21 sui **529 scene in `CONDITIONAL_REFERENCE_CHECK`**
aggiungendo tre gate, tutti calcolabili prima di qualunque richiesta remota:

1. `sicd_size_bytes` o `cphd_size_bytes` non nulli (disponibilità **pubblica**,
   non dichiarazione STAC);
2. differenza assiale onda-range **≤ 35°**;
3. almeno **10 lunghezze d'onda nella ROI**, cioè `δL/L ≤ 0.1`.

E poi, sulle sopravvissute, interrogare la boa per `Hm0` e richiedere
**`Hm0 ≥ 1.5 m`** — soglia descrittiva, non calibrata, ancorata al fatto che
Vandenberg a 1.99 m era già marginale.

I gate 1–3 non costano nulla e riducono i 529 prima di spendere richieste.

## File

`code/analyze_block24_shortlist_triage.py`,
`Block24_shortlist_triage/BLOCK24_SHORTLIST_TRIAGE.json`, questo report.
