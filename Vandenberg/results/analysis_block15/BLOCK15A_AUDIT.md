# BLOCK 15A — audit operativo multicomponente

Data: 2026-09-11. Esito: audit completato; nessun nuovo stimatore o risultato scientifico prodotto. Stack iniziale consigliato: BP12, non perché concordi con boa o DEM, ma per disponibilità, tracciabilità temporale e supporto più circoscritto.

## 1. Stato e perimetro

- Root effettiva: `D:\Dati Tesi\Umbra`; repository `davidedalmazzo/bathymetry_thesis`.
- Branch `main`, commit `d5fab7b4c49bb9c5d4a0a8dbfdb0b2dc316a2fdf`; worktree inizialmente pulito, `main...origin/main` senza divergenza indicata dallo stato locale. Nessun fetch necessario.
- Interprete prescritto disponibile: `.venv-umbra-thesis/Scripts/python.exe`, Python 3.13.9 (Anaconda), NumPy 2.5.2, SciPy 1.18.1, SarPy 2.0.1, pytest 9.1.1. `rasterio` e `pyproj` non disponibili: non installati né sostituiti con un altro ambiente.
- Letti AGENTS, README, TASK_SPEC, WORKLOG e checkpoint 1–12, quindi codice e artefatti pertinenti 11–14. Le proposte storiche di formazione/inversione non sono autorizzazioni operative attuali. WORKLOG terminava al Block 5 e non rappresentava da solo lo stato completo del progetto.
- CPHD, SICD, stack BP12/BP13 e prodotti SICD locali presenti. Nessun download, formazione, sweep, inversione, commit o push. Conservati i risultati precedenti e `T_SAR = 17.902230457 s`.

L'inventario JSON allegato distingue verifiche attuali (`verified_*`, header e stat), dichiarazioni storiche (`declared_*`, manifest e piani) e informazioni mancanti. I manifest incorporati conservano anche affermazioni storiche NON avallate da questo audit. Nessun nuovo hash integrale dei radar o stack. La verifica di header non certifica l'integrità di tutti i pixel.

## 2. Input effettivamente disponibili

| Candidato | File relativo a Vandenberg | Byte verificati | Header verificato | Utilità e limite |
|---|---|---:|---|---|
| BP12 | results/block12_backprojection/BLOCK12_SUBLOOKS_complex64.npy | 9,584,768 | 32 × 288 × 130, complex64 | Primo confronto controllato |
| BP13 | results/block13_backprojection/BLOCK12_SUBLOOKS_complex64.npy | 19,968,128 | 32 × 600 × 130, complex64 | Sensibilità spaziale successiva; profondità parametrica |
| SICD | 2025-02-16-18-55-44_UMBRA-10_SICD.nitf | 11,478,596,733 | 13310 × 107800, RE32F_IM32F | Header NITF aperto con SarPy, nessun pixel letto |
| CPHD | 2025-02-16-18-55-44_UMBRA-10_CPHD.cphd | 140,554,224,768 | Dimensioni segnale dichiarate 165924 × 105840, CF8 | Solo TxTime PVP letto; segnale non letto |
| Sliding SICD nearshore | results/block4_sliding_complex + results/sublooks_complex | 92,160,128 per look | 1200 × 9600, complex64 | Tutti gli 11 look disponibili, 8 nuovi + 3 riusati |
| Sliding SICD terra | stesse cartelle | 150,995,072 per look | 1536 × 12288, complex64 | Tutti gli 11 look disponibili |
| Nominali SICD | results/sublooks_complex | come sopra | 3 look per nearshore/offshore/terra, più full-aperture | Complessi conservati; non stesso supporto BP |
| Block 7 sea-surface | results/block7_enlarged_nominal_sea_surface | 6,896,204 per file | 3 × (1761 × 979), float32 | Intensità, NON stack complesso né sequenza di 32 look |

Disponibili anche i tre prodotti Block7 precedenti, 2140 × 1119 float32 (9,578,768 byte ciascuno): non confonderli con la revisione sea-surface. Archivi spettrali Block4 nearshore/terra e mappa Block6 presenti (circa 1.47/1.44/3.76 MB); utili per regressione storica, non sostituti dei complessi BP. Percorsi individuali, dimensioni e manifest associati sono nell'inventario.

### Tempi e formazione BP

Entrambi i manifest `BLOCK12_SUBLOOK_MANIFEST.json` rimandano a `code/form_block12_backprojection.py::_form`, con kernel `code/umbra_sar/backprojection.py::backproject` e assegnazione `disjoint_look_assignment`.

- 32 intervalli richiesti uniformi, ciascuno 0.7043998823333333 s; estremi TxTime 0.0029798746666667–22.543776109333333 s, riferiti a collection start 2025-02-16T18:55:33Z.
- Verifica attuale sul campo TxTime del PVP: span effettivo primo–ultimo impulso per look 0.704124762666666–0.704386746666668 s; 4280–5274 impulsi/look, totale 165924; assegnazione esclusiva, nessun impulso condiviso. Tutti i conteggi coincidono con i manifest.
- Centri medi verificati: 0.355347310216794–22.191503827842272 s; baseline tra centri 21.83615651762548 s. Tutti i 32 centri e gli estremi sono registrati nel JSON. Scarto massimo rispetto ai manifest 7.82e-14 s. Non assumere campionamento perfettamente uniforme dei centri: usare la lista effettiva.
- Tre quantità distinte: processed aperture SICD **18.068061721230308 s**; dwell CPHD **22.540812513364376 s**; span TxTime degli impulsi **22.540796234666665 s**.
- La verifica PVP usa una mappa read-only del blocco metadati da 62,387,424 byte, non del segnale da 140 GB. Conferma la partizione ricostruibile, non prova retroattivamente ogni operazione numerica di formazione.

Griglia BP12 1440 × 650 m; BP13 3000 × 650 m; passo 5 m. Distanza tra centri estremi 1435/2995 × 645 m: non confondere estensione NΔ con (N−1)Δ. Centri UTM rispettivi (715510.6102416331,3827627.093742074) e (714742.85,3827489.45). Prima dimensione lungo bearing 79.8357237°, seconda lungo bearing +90°. In `build_ground_grid` il bearing è rispetto al nord della griglia UTM: una direzione geografica vera richiede la convergenza del meridiano. Il codice usa WGS84, UTM 10N, quindi EPSG:32610 implicito, non un CRS completo registrato nel manifest. Superficie costante HAE −36.376 m: zero NAVD88 approssimato con GEOID18, non livello marino istantaneo misurato.

Il kernel somma uniformemente gli impulsi, senza taper temporale o normalizzazione per conteggio; IFFT di range, interpolazione Catmull–Rom, portante +1. FFT 262144, passo del ritardo espresso in range 0.07076133 m, oversampling 2.4768; finestre di ritardo ±900 m BP12 e ±2400 m BP13. **Nessuno di questi passi è una PSF misurata.** La risoluzione fisica 2D dei look brevi non è certificata; griglia a 5 m può campionare una risposta radar più fine senza un esplicito filtro antialias. Numero variabile di impulsi e risposta del bersaglio possono influenzare ampiezze/SNR e tempi efficaci. Media TxTime esatta non significa centro temporale esatto dell'osservabile ondoso.

### Prodotti SICD e geometria

Header attuale: RGAZIM/SLANT; asse 0 range, asse 1 azimuth; Row.SS=0.167993380972 m, Col.SS=0.056435265164 m. ImpRespWid dichiarate 0.186031670254/0.062495001761 m nella Grid del prodotto completo: non risoluzione dei sub-look né passo terrestre. SVA dichiarata su entrambe le direzioni, senza WgtFunct; non blocca i test ma non è invertibile a partire dai soli metadati disponibili. Non basta per attribuire causalmente tutto il bias a SVA.

`BLOCK4_SLIDING_MANIFEST.json` e `metadata/BLOCK4_SLIDING_LOOK_PLAN.json`: 11 look cronologici; centri PVP 3.2428993865–14.8322572632 s, separazioni circa 1.156–1.163 s; banda 28638 bin, richiesta nominale 6 s, realizzata nominale 5.999920588736 s, supporto fisico circa 5.784–5.828 s. Sovrapposizione Doppler adiacente circa 80%; non identifica automaticamente la correlazione statistica. Taper Tukey alpha 0.25 con normalizzazione energetica. Gli anchor 1/6/11 riusano i nominali Block3 in ordine 3/2/1. Formazione storica: `code/form_block4_sliding_looks.py`, presente nel progetto; nessun rilancio autorizzato qui.

`roi/ROIS.json` conserva bounds, Jacobiani EN e orientamenti locali. Nearshore: circa 538.44 × 542.28 m, bearing locale row 281.1786273°, col 191.4579829°; terra circa 693.13 × 693.60 m. Queste ROI storiche usano HAE +101.5247567 m, non la superficie BP −36.376 m; non confrontarle come impronte perfettamente co-localizzate. Il Block7 sea-surface ha una diversa geolocalizzazione. `SICD_METADATA.json` contiene ancora `downloaded:false`: stato storico della prima estrazione, smentito dall'esistenza attuale del file completo, non da correggere in questo audit.

## 3. Rilievi: bug confermati, limiti e dubbi

### A. Coerenza Block12 — bug confermato

`code/analyze_block12_phase_slope.py`, main, righe 108–135: fase da singolo bin `F_t * conj(F_ref)`; la coerenza endpoint è `abs(a*conj(b))/sqrt(abs(a)^2*abs(b)^2 + 1e-30)`. Per un'unica realizzazione non nulla vale praticamente uno: non misura la ripetibilità. È **modulo**, non magnitude-squared coherence (MSC). Il gate `coherence >= min_coherence` non discrimina decorrelazione.

Impatto: `valid_mask`, selezione del picco, lobo a potenza >5%, statistiche del lobo e confronto di dispersione dipendono da questo gate. La mappa di pendenza numerica non diventa aritmeticamente falsa per questa identità, ma la qualificazione dei suoi bin come affidabili non è supportata. Picco, coppie e derivati dovranno essere rivalutati con gate significativo, in nuovi output: non si può anticipare quanto cambieranno.

`code/analyze_block12_dispersion.py::smooth` e main, righe 53–60, 95–123: media boxcar 3×3 del cross e delle potenze **prima** del rapporto. Restituisce ancora modulo gamma, NON gamma². Soglia 0.25 in modulo equivale a MSC 0.0625, non MSC 0.25. Lo smoothing usa np.roll periodico; il supporto utile va tenuto lontano dai bordi e dalle controparti coniugate. La fase continua a essere stimata sul singolo bin, non sul cross mediato.

Il secondo script seleziona 60–300 m, semipiano orientato al picco, potenza >15%, R²>0.97 e gamma>0.25; il primo usa 40–500 m e il lobo >5%, senza deduplicare i coniugati. Non sono soltanto due versioni dello stesso gate. La nuova selezione alimenta i modelli di `BLOCK12_DISPERSION.json`, ma **non riscrive** `BLOCK12_PHASE_SLOPE.json`, la precedente mappa NPZ o il checkpoint. Entrambi i rami richiedono una futura valutazione controllata, non la sostituzione retroattiva dei risultati congelati.

### B. Provenienza Block14 — lacuna confermata

`code/analyze_block14_nonlinearity.py`, payload righe 228–247, produce cutoff, fondamentale, armoniche e regressione anisotropica semplice. Non produce `controlled_for_wavelength`, `model_comparison` né le interpretazioni aggiunte in `results/analysis_block14/BLOCK14_NONLINEARITY.json` (in particolare righe 47–78).

Ricerca dei nomi e della frase “C wins on every” nei file Python/JSON/Markdown locali e nei tre commit raggiungibili: occorrenze soltanto nel JSON importato. Per quei campi: **provenienza non ricostruita nel materiale disponibile**. Non è dimostrato che siano errati o manuali; manca il generatore riproducibile. Non usare il verdetto aggiunto “bias moltiplicativo, non Doppler” come conclusione validata. Rilanciare lo script attuale perderebbe quei campi: non farlo sopra il file storico.

### C. dem_depth_m Block13 — provenienza parametrica confermata

`code/analyze_block13_sliding.py`, argomenti e main righe 105–117, 163–172: `dem_depth_m = dem_edge_depth_m + dem_gradient*(length_parallel/2 - offset)`, default 10.11 m e 8.79e-3 m/m. Nessuna apertura o campionatura raster; il nome “DEM” e la curva tratteggiata in figura possono farla scambiare per una misura locale. Il gradiente è coerente con statistiche Block7 (~−8.787 m/km), ma il codice non registra la catena di estrazione del valore al bordo o un manifest completo dei parametri di profondità. Non attribuire precisione raster a questo profilo, soprattutto nei 3 km estesi.

Disponibili nove TIFF `bathymetry/10SGD*.tif`, VRT e metadati XML/HTML. Prodotto storico dichiarato: NOAA InPort 49417, 2009–2011 CA Coastal California TopoBathy Merged Project DEM (Smoothed with Voids), 1 m, NAD83/UTM10N EPSG:26910 (etichetta NSRS2007), NAVD88 EPSG:5703. Non rinominare questo prodotto CUDEM. Età locale per pixel non documentata; metadata storici riportano pubblicazione 2014 e conversione COG 2024.

`code/analyze_block7_bathy_residual.py::sample/roi_stats/main`, righe 26–39, 64–78: merge con nodata NaN, campionamento nearest, fuori copertura NaN, statistiche solo finite. `plan_block7_support.py::sample_nearest/main`: criteri acqua su campioni finiti ed elevazione <−2 m; screening iniziale 10 m, verifica 5 m. Non è una prova continua dell'intero rettangolo. Nelle statistiche a 2 m il supporto massimo ha valid_fraction 0.99999149, non esattamente uno; originale 0.98263913 e alcune quote positive. Nessun riempimento dei void o correzione di marea applicata dagli script. `-elevation_NAVD88` non è profondità istantanea né MLLW. Trasformazioni VDatum delle fonti sono dichiarate dal prodotto, non una correzione all'ora SAR.

Limite attuale: rasterio/pyproj assenti; verificati esistenza/byte dei raster, non ricampionati né riletti gli header raster con quei pacchetti. Inoltre le coordinate WGS84 UTM del codice BP e NAD83 del raster sono usate come numericamente compatibili senza una trasformazione datum esplicita in questi script. Impatto metrico da quantificare, non assunto nullo. Nessuna inversione o nuova quota calcolata nell'audit.

### D. Stima della frequenza e dipendenza

| Blocco / funzione | Osservabile e riferimento | Fit, segno, smoothing | Dipendenze e limiti |
|---|---|---|---|
| B11 `analyze_block11_energy_centroid.py::main/ols_slope_map` | Fasi patch già salvate da B6, 11 look; rimappa tempi con energia Doppler dei chip | OLS con intercetta; pendenza con segno, omega derivata in modulo | Centroidi energetici influenzati da spettro scena e crop; non prova che siano il tempo fisico della componente |
| B11 `analyze_block11_pairwise_omega.py::main/weighted_line` | 55 differenze di fasi B6 riferite al primo look | abs(delta_phase/delta_t), regressioni peso delta_t² | Non calcola cross patch diretti fra ogni coppia; errori denominati naive, ma verdetto usa 3 SE |
| B12 phase_slope main | 32 coefficienti singoli, riferimento centrale indice 16, tempi ordinati | Unwrap incondizionato; OLS uniforme, RMSE/R², omega=abs(slope); Tukey spaziale 0.1 + detrend piano | 496 differenze di fasi comuni, pesi delta_t²; lobo iniziale include coniugati |
| B12 dispersion main | Stessa fase raw per bin e riferimento centrale | Smoothing 3×3 solo per gamma; gate sopra descritto; fit modelli pesato in potenza | Bin vicini/finestrati non indipendenti; selezione non prova lobo connesso/risolto |
| B13 sliding main | Picco massimo selezionato per finestra spaziale, non per tempo; riferimento indice 16 | Piano + Tukey 0.2, singolo bin, unwrap incondizionato, OLS, abs(slope) | Nessun gate di coerenza; finestre default 1000 m/step250 m condividono il 75% del supporto; CV non è errore indipendente |
| B14 main | Ultimi 1500 m di BP13; raw bin, riferimento indice 16 | Piano + Tukey 0.2, unwrap e OLS; abs(slope); gate potenza/R² per anisotropia | Nessuna coerenza; errore regressione profondità-angolo tratta bin come indipendenti; armoniche ricercate entro intorni, non punti esattamente n*k |

La convenzione effettiva di fase resta `F_secondary * conj(F_reference)`; convertirla in |s| perde l'informazione di propagazione e deve essere esplicito. B11 eredita smoothing patch e controlli B6; non li ripete sui nuovi tempi. B12–14 non sono implementazioni equivalenti allo stimatore patch B4/B6.

Per singoli coefficienti non nulli vale algebraicamente arg(Fj*conj(Fi)) = wrap(phi_j−phi_i). Per cross **mediati su patch**, arg(sum Fj*conj(Fi)) non è in generale la differenza di argomenti dei cross mediati con un riferimento comune. Di conseguenza chiusura costruita per differenza non è verifica indipendente di coerenza fisica. Le coppie condividono look e riferimenti: 55 coppie da 11 tempi o 496 da 32 tempi non sono 55/496 osservazioni indipendenti, neppure con aperture disgiunte.

Conclusioni storiche da limitare, senza modificarle: B11 non esclude causalmente overlap/decorrelazione con la sola assenza di trend e SE naive; B12 non dimostra lobo risolto contando bin selezionati, né isola l'effetto SVA cambiando insieme formazione, ROI, durata, pesi e stimatore. La media TxTime è verificata, ma non elimina ogni bias temporale. B14 cutoff/armoniche possono essere influenzati da risposta strumentale, leakage, scelta dei massimi e campo ondoso: non bastano a identificare univocamente una non linearità. Le conclusioni aggiunte senza generatore restano sospese.

## 4. Test attuali e copertura reale

Eseguito nell'ambiente prescritto, senza scrittura bytecode/cache pytest:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv-umbra-thesis\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
```

Risultato corrente: **57 passed in 5.61s**, exit 0; falliti 0, saltati 0, test raccolti non eseguibili 0. Non è un riuso del vecchio “57 passed”. Ispezionati conftest, test e accessi prima della verifica conclusiva; nessun generatore di report storico eseguito. La suite legge anche piccoli artefatti, e `test_block7_geolocation_support_and_formed_arrays` scansiona tre intensità da circa 6.9 MB ciascuna per `isfinite`; non legge integralmente SICD/CPHD o stack complessi multi-GB. Non avvia formazione o download.

| Copertura | Evidenza | Cosa NON valida |
|---|---|---|
| FFT/IFFT, segno, bande, durate | test_subaperture.py, cinque classi Test01–05, confronto SarPy reale Col.Sgn=-1 | Non una validazione della formazione BP |
| Phase sign, patch, pendenza, shift | test_wave_analysis.py; test_phase_slope_map.py | Non tutte le implementazioni raw B12–14 |
| Coerenza e gate patch | test_independent_anchor_coherence_rejects_patch_decorrelation | Non intercetta la coerenza degenere nel main B12 o soglie modulo/MSC |
| Tempi | separazione dwell/apertura e ordinamento nominale; guardrail artefatti | Nessun test dedicato dell'inversione reale Doppler–PVP o partizione BP; verifica PVP attuale separata dalla suite |
| Miscele/dispersione | test_physical_identification.py; test_block9_synthetic_validation.py (sei modi, controlli statico/costante/lineare, surrogate complesso) | Non copertura generale di componenti vicine non risolte e leakage off-grid |
| Modello SAR minimo | test_block10_ocean_sar_forward.py, velocità orbitale, RAR, bunching, guardrail | Approssimazione di immagine/intensità, non simulatore phase-history CPHD focalizzato |
| Regressioni congelate | test_block5/6/7_artifacts e parte B9/B10 | Confermano valori/file già prodotti, non rigenerazione indipendente della scienza |
| Retroproiezione CPHD | Nessun test pytest importa backprojection o form_block12 | Overview e smoke storici non costituiscono test automatici attuali di fase/PSF/dinamica |

Restano non rieseguite, perché fuori perimetro, formazione CPHD, analisi B11–14 e campionatura raster dipendente dai pacchetti assenti. Non sono “test saltati”: non appartengono ai 57 test raccolti. La presenza del bug B12 con suite verde è coerente con questa lacuna di copertura.

## 5. Solo proposta Block15B

1. Usare **BP12** completo, 32 × 288 × 130, 5 m, tempi medi verificati. Supporto storico più documentato e meno esteso di BP13; nessuna selezione per accordo esterno. BP12 resta dataset development/debug, non nuova validazione oceanografica. BP13 e SICD restano controlli successivi, non da mescolare nel primo confronto.
2. Piccolo modulo comune, ad esempio `umbra_sar/frequency_comparison.py`: costruzione unica di intensità/detrend/finestra/spettro, convenzione signed, definizione esplicita modulo/MSC, maschera comune e selezione fissata senza guardare boa/profondità. Non riscrivere la libreria né sovrascrivere B12–14.
3. Riutilizzare `wave_analysis.coherent_patch_cross`, `local_coherent_phase_slope_map`, `linear_phase_fit` (OLS/HAC), controlli e deduplicazione coniugati di `synthetic_validation`; riutilizzare lettura manifest e partizione tempi, senza richiamare backproject. Le opzioni independent_indices della funzione patch vanno configurate esplicitamente per 32 tempi, non lasciate al default degli 11 look.
4. Confrontare sullo STESSO input e sugli stessi centri k: raw-bin slope come baseline, fase di cross patch con riferimento comune, cross patch calcolati direttamente per coppia/adiacenti. Conservare signed slope, Cij, MSC, residui e ragioni di esclusione. Non identificare automaticamente |s| con frequenza oceanica. Non contare i bin di una patch o coppie condivise come repliche indipendenti.
5. Test mirati prima dei dati: identità degenere a singolo bin; media prima del rapporto; gamma vs gamma²; rumore decorrelato e zero power; inversione ordine/cambiamento riferimento; differenza fra cross patch diretto e fasi comuni; unwrap ambiguo con rifiuto; miscela vicina e off-grid/leakage su più seed; variazioni piccole e prefissate di patch. Separare questi test degli stimatori da una futura validazione end-to-end CPHD non compresa nel 15B minimo.
6. Riportare dipendenze: SE OLS solo nominale, HAC non garanzia con serie corta; eventuale resampling per unità temporali/spaziali appropriate, non bootstrap ingenuo delle 496 coppie. Per il primo confronto, mostrare anche sensibilità a riferimento/patch e dimensione effettiva del supporto.
7. Output nuovi circoscritti: manifest input/config/versione, tabella confronto firmata per bin/patch, diagnostica coerenza/unwrap/residui, report test e decisione su quali stimatori siano confrontabili. Escludere dal gate boa, DEM parametrico, campi B14 senza provenienza e qualunque inversione. Non è necessario correggere ora le statistiche batimetriche per confrontare stimatori SAR-only.

Ulteriore rischio operativo confermato: `FORMA_BLOCK12.bat`, `FORMA_BLOCK13.bat` e LEGGIMI storico puntano a `.venv` con fallback al Python di sistema; non rispettano l'interprete attuale AGENTS. Non eseguiti né modificati. Un eventuale futuro launcher deve usare esplicitamente `.venv-umbra-thesis`, senza fallback silenzioso.

## Stop

Consegnati `BLOCK15A_AUDIT.md` e `BLOCK15A_INPUT_INVENTORY.json`; WORKLOG aggiornato solo in append. Nessuna modifica al codice, ai test o ai risultati congelati. Block15B richiede una nuova autorizzazione.
