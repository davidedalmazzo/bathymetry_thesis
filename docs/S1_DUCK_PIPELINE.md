# Duck / Sentinel-1: pipeline spaziale e ground truth (Block 35–38)

Documento di sintesi degli script aggiunti tra il 19 e il 22 settembre 2026 e di
cosa è stato ottenuto. I dati grezzi (SAFE, TIFF, ZIP, BAG, cache) non sono
versionati; tutto si rigenera con i comandi sotto.

## 1. Cosa è stato fatto, in ordine

| Block | Contenuto | Esito |
|---|---|---|
| 35 | Ricerca CDSE di scene S1 IW su Duck (ott. 2021), confronto con spettri e survey FRF | scelta la scena S1A 2021‑10‑28 23:06 (orbita 40326) |
| 36 | Preflight delle sole annotazioni (manifest, annotation/calibration/noise IW1‑3) | ROI in IW3, burst 0, geometria locale |
| 37 | Download completo SLC (7,8 GB, MD5 verificato) e prima prova spaziale | **superato**: vedi nota di geolocalizzazione |
| 38 | Script generico a transetti (metodo Mudiyanselage et al. 2024), baseline GRD, ground truth, verifica in avanti su tutta la scena | λ SAR ≈ λ prevista, mediana +3,6 %, fondali 7–27 m |

### Errore di geolocalizzazione trovato (Blocks 36/37)
`s1_iw_annotation.GeoGrid` interpola la griglia di geolocalizzazione IW SLC in
*numero di riga*, ma le righe della griglia sono agli inizi burst e i burst si
sovrappongono: il tempo azimutale risulta compresso del 12 %. A Duck la ROI del
Block37 era ~1,4 km più a nord di quanto previsto. Corretto in
`s1_iw_geometry.py` (interpolazione in tempo di burst); verificato contro la
linea z≈0 del survey FRF (scarto mediano 0,8 campioni contro 74). Dettagli:
[NOTE_S1_GEOLOCATION_BURST_TIME.md](NOTE_S1_GEOLOCATION_BURST_TIME.md). I file
congelati del Block37 non sono stati modificati.

## 2. Script

### Dati SAR
- **`code/download_s1_safe_members.py`** — scarica da CDSE solo i membri SAFE
  necessari (manifest, annotazioni, measurement di una polarizzazione) via
  endpoint *Nodes*, con ripresa HTTP Range e verifica MD5 dal manifest.
  (L'endpoint del prodotto intero risponde 501 a Range.)
- `code/download_block37_s1.py`, `code/download_s1_full_safe.py`,
  `code/prepare_block37_safe.py` — download/estrazione dell'archivio completo.
- `code/cdse_credentials.py` — credenziali CDSE da `.env` (escluso da Git).

### Geometria e spettro
- **`code/s1_iw_geometry.py`** — geolocalizzazione IW SLC corretta (tempo di
  burst) e `GrdGeometry` per prodotti GRD.
- **`code/s1_paper_peak.py`** — identificazione del picco del paper: 20 livelli
  di contour, blob sopra il livello massimo, centroide del blob più grande più
  vicino all'origine; DTFT su campioni nativi (nessun ricampionamento), maschere
  di ricerca, media mobile, Eq. 5/6.

### Script principale (generico, nessuna configurazione per sito)
- **`code/s1_transect_bathy.py`** — `SAFE + --bbox`:
  mappa σ0 multilook → maschera terra/mare istantanea dal SAR (Otsu) → linea di
  costa → transetti normali verso il largo → finestre ogni `--step` m su pixel
  nativi in un solo burst → spettro → picco → media mobile → profondità (solo se
  `--period` da boa). Legge SLC e GRD.
  Opzioni chiave: `--window`, `--alongshore-average N` (media degli spettri di
  transetti vicini, necessaria perché il periodogramma single‑look è χ²(2)),
  `--save-spectra`, `--chunk I N` / `--finalize N` (esecuzione a pezzi).
  README: [code/README_S1_TRANSECT_BATHY.md](../code/README_S1_TRANSECT_BATHY.md).

### Ground truth
- **`code/frf_ground_truth.py`** — un comando per orario + bbox: osservazioni FRF
  (onde con spettri, correnti, vento, livello) tramite il client FRF esistente,
  survey DEM FRF più vicino, BlueTopo, CUDEM e rilievi storici; fonde tutto su
  griglia UTM ordinando le fonti per **accuratezza misurata** (FRF > BlueTopo
  moderno > rilievi storici corretti > BlueTopo interpolato > CUDEM) e scrive
  l'incertezza empirica di ogni cella (NMAD contro i dati di rango superiore).
  README: [code/README_FRF_GROUND_TRUTH.md](../code/README_FRF_GROUND_TRUTH.md).
- `code/frf_client/dem.py` — survey DEM FRF via THREDDS nel client esistente.
- `code/coastal_dem.py` — NOAA CUDEM, NOAA BlueTopo (con incertezza e rilievo di
  origine per cella), griglie storiche (`legacy_spec`, es. USGS OFR 2011‑1015).

### Verifica
- **`code/forward_lambda_check.py`** — verifica in avanti (nessuna inversione):
  per ogni finestra SAR su batimetria certificata (incertezza empirica ≤ 0,5 m)
  lo spettro E(f) di una boa viene portato in E(k) alle profondità della
  finestra e confrontato con lo spettro SAR.
- **`code/forward_lambda_combine.py`** — unisce le verifiche usando per ogni
  finestra la boa più vicina in profondità.
- `code/duck_frf_compare.py` — confronto puntuale con il survey (solo Duck).

## 3. Risultati principali (Duck, 28/10/2021)

- **Batimetria**: lidar USACE 2019 vs survey FRF 2021 +0,20 m, NMAD 0,15 m;
  USGS `nhatt` (1999–2002) ha un offset di +0,70 m verso i dati moderni, dopo la
  correzione NMAD 0,26–0,30 m; copre il 94 % della fascia 3–9 km.
- **GRD vs SLC**: λ mediata per fascia concorda entro 1–4 % (controllo
  indipendente della catena SLC). Il paper applicato alla lettera (finestre
  1280 m) è stabile ma non risolve il gradiente cross‑shore a Duck.
- **Verifica in avanti** (4465 finestre, 7,2–27,5 m): λ SAR / λ prevista − 1
  mediana +3,6 %, NMAD per finestra 20 %; per fascia di 1 m entro ±5 % salvo le
  fasce riferite all'AWAC (10–15 m, +8…+17 %).
- **Limite dominante**: il periodo. Le quattro boe danno picchi 10,8–12,9 s e
  cambiarle sposta λ prevista di ±10 %, contro ≤ 1 % dovuto alla batimetria.
  È l'argomento per stimare ω dal SAR (prossimo passo: sovrapposizione fra burst).

## 4. Riprodurre

```powershell
# ground truth (rete FRF su tranche nominata)
python code\frf_ground_truth.py --timestamp-utc 2021-10-28T23:06:39Z --bbox -75.79 36.15 -75.56 36.26 `
  --out outputs\ground_truth_s1a_20211028_ext20 --acquisition-id s1a_20211028_duck --tranche gt_20211028 --new-tranche `
  --legacy-grid https://pubs.usgs.gov/of/2011/1015/data/bathymetry/innershelf/nhatt.zip,-0.128,nhatt,2001 `
  --legacy-grid https://pubs.usgs.gov/of/2011/1015/data/bathymetry/nearshore/vims_2002.zip,-0.623,vims_2002,2002
# SAR (a pezzi se la shell ha limiti di tempo)
python code\s1_transect_bathy.py <SAFE> --bbox -75.79 36.15 -75.56 36.26 --sea-side E --alongshore-average 4 `
  --save-spectra --window 512 --offshore 250 6000 --out duck_frf\Block38_s1_transects_duck\ext_near
python code\s1_transect_bathy.py <SAFE> --bbox -75.79 36.15 -75.56 36.26 --sea-side E --alongshore-average 4 `
  --save-spectra --window 1024 --kmax 0.15 --step 100 --transect-spacing 500 --offshore 5000 20000 `
  --out duck_frf\Block38_s1_transects_duck\ext_far
# verifica
python code\forward_lambda_check.py --run duck_frf\Block38_s1_transects_duck\ext_near `
  --ground-truth outputs\ground_truth_s1a_20211028_ext20 --reference FRF:waverider-17m `
  --out duck_frf\Block38_s1_transects_duck\ext_near\forward_waverider-17m
python code\forward_lambda_combine.py --out duck_frf\Block38_s1_transects_duck\forward_combined `
  --run near:duck_frf\Block38_s1_transects_duck\ext_near --run far:duck_frf\Block38_s1_transects_duck\ext_far `
  --prefer far --prefer-min-depth 19 --gauge 8m-array=8 --gauge awac-11m=11.9 --gauge waverider-17m=18 --gauge waverider-26m=26
```

Test: `tests/test_s1_transect_bathy.py`, `test_s1_paper_peak.py`,
`test_ground_truth.py`, `test_forward_lambda_check.py` (+ test Block 36/37).
