# Checkpoint 1 — audit e metadata, prima delle elaborazioni pesanti

Data: 2026-08-29. Workspace esclusivo: `D:\Dati Tesi\Umbra`.

## 1. Contenuto rilevante iniziale

Sono stati trovati cinque file: CPHD originale da 140.55 GB, GEC da 272 MB,
`sicd_subaperture.py`, `download_vandenberg_sicd.bat` e
`README_Vandenberg_SICD.md`. Non erano presenti SICD/NITF, STAC locale,
`cphd_probe.py` o `gec_look.py`. L'inventario esatto è in
`FILE_INVENTORY_INITIAL.md`.

La task caricata è stata copiata byte-per-byte in `TASK_SPEC.md`; gli SHA-256 di
input e copia coincidono.

## 2. Conformità filesystem

Non è stato creato, modificato, cancellato, installato o scaricato alcun file
fuori da `D:\Dati Tesi\Umbra`. File caricati e interpreti su C: sono stati usati
solo in lettura. CPHD, GEC e tre file forniti non sono stati modificati.

## 3. CPHD

- Percorso: `Vandenberg/2025-02-16-18-55-44_UMBRA-10_CPHD.cphd`
- Dimensione: 140,554,224,768 byte, corrispondenza esatta con l'atteso.
- CPHD 1.1.0; header, XML e PVP coerenti; validazione semantica SarPy `True`.
- Il signal block dichiarato è 140,491,169,280 byte, termina esattamente a EOF e
  coincide con 165,924 x 105,840 x 8 byte.
- Il signal block non è stato letto. Sono stati letti soltanto header, XML e i
  PVP da 62,387,424 byte tramite memory map.

Report: `Vandenberg/metadata/CPHD_REPORT.md` e
`Vandenberg/metadata/CPHD_METADATA.json`.

## 4. SICD

Il SICD completo non è locale e non è stato scaricato.

Il listing ufficiale Umbra conferma il key pubblico
`2025-02-16-18-55-44_UMBRA-10_SICD.nitf`, 11,478,596,733 byte, ETag
`f06d503551fb567303477152aee18652-219`. Lo STAC usa internamente il nome di
produzione `2025-02-16-18-55-33_UMBRA-10_SICD_MM.nitf`; entrambi si riferiscono
al collect UUID `9d8283d8-550d-4435-899f-5483d2c1abcc`.

Con quattro HTTP range per circa 1.10 MB totali sono stati recuperati header
NITF, secondo image subheader e XML SICD. Il NITF dichiara la stessa lunghezza
dell'HTTP e due segmenti immagine da 11,595 + 1,715 righe.

Report: `Vandenberg/metadata/SICD_REPORT.md`, XML estratto
`SICD_METADATA.xml` e JSON `SICD_METADATA.json`.

## 5. Audit preliminare dei file forniti

Audit completo: `AUDIT_CODE.md`.

Risultati principali:

- Il `.bat` punta al key pubblico corretto, ma manca `curl --fail`, non esegue
  HEAD/preflight, non verifica spazio, lunghezza finale, UUID, ETag o contenuto.
- Il README consiglia un'installazione pip non isolata e una ROI azimutale prima
  della FFT; entrambe sono incompatibili con i vincoli della task.
- Lo script determina correttamente axis 1 per RGAZIM, ma per questo SICD usa la
  direzione FFT fisica sbagliata: Col.Sgn=-1 richiede `fft_sicd`, cioè NumPy FFT,
  mentre lo script usa IFFT. Il round-trip interno non rileva l'errore perché la
  coppia di trasformate è comunque inversa.
- La ROI 1 km pre-FFT contamina lo spettro Doppler e richiede già circa 0.84 GB
  per ogni array complex64; il picco RAM è di vari GB.
- Mancano Tukey, normalizzazione/ENBW, centri e overlap arbitrari, chunk in range,
  test di asse/banda/cross-spettro, coregistrazione, coerenza e land control.

## 6. Ambiente Python

- Eseguibile: `D:\Dati Tesi\Umbra\.venv\Scripts\python.exe`
- Python 3.11.15
- NumPy 2.4.6; SciPy 1.17.1; SarPy 2.0.1; Matplotlib 3.11.1; h5py
  3.16.0; lxml 6.1.2; sarkit 1.8.1; pytest 9.1.1.
- TEMP/TMP: `D:\Dati Tesi\Umbra\_tmp`; pip cache:
  `D:\Dati Tesi\Umbra\_cache\pip`.

Dettagli: `ENVIRONMENT.md`.

## 7. Metadati principali CPHD misurati

- Collector `Umbra-10`, monostatico, SPOTLIGHT, dominio FX, SGN -1, VV.
- CollectionStart `2025-02-16T18:55:33.000000Z`.
- 1 canale `Primary`; 165,924 vettori; 105,840 campioni; CF8.
- TxTime PVP: 0.002979874667–22.543776109333 s; span 22.540796234667 s.
- DwellTime/SRPDwellTime: 22.540812513364 s. Il valore preliminare ~22.6 s è
  confermato soltanto come arrotondamento.
- Frequenza centrale 9.799978362629 GHz; banda 854.213202372 MHz.
- PRF non costante: rate locale nominale mediano ~7,470.715 Hz; rate medio dei
  vettori memorizzati ~7,361.009/s. La differenza deriva da 2,281 numeri di
  impulso mancanti nella sequenza continua 53–168,257.
- SRP/IARP: lat 34.581401673389°, lon -120.627098686583°, HAE 101.524757 m.
- Right-looking; incidenza 21.908539942°, graze 68.091460058°, viewing azimuth
  105.848355722°, slant range 610,631.063 m.
- Ground track derivato dalla velocità: 191.199523702°; asse non orientato
  11.199523702°. Le stime preliminari geometriche sono confermate.
- PVP disponibili: Tx/Rcv time, position, velocity, antenna frames/boresight,
  SRPPos, aFDOP, aFRR1/2, FX1/2, TOA/TOAE, troposfera, scale factors, SIGNAL e
  PulseNumber.

## 8. Metadati principali SICD

- SICD 1.3.0 XSD-valid; complex float32 `RE32F_IM32F`.
- ImageData: 13,310 righe x 107,800 colonne; SCP pixel (6,655, 53,900).
- Grid: RGAZIM, SLANT; Row SS 0.167993381 m; Col SS 0.056435265 m.
- Row DeltaK1/2: -2.381046192 / +2.381046192 1/m.
- Col DeltaK1/2: -7.087766822 / +7.087766822 1/m.
- Row e Col DeltaKCOAPoly sono zero; supporto processato Col = 80% della FFT,
  circa 86,240 bin.
- Timeline.CollectDuration: 22.547940447 s.
- PFA ImageFormation: TStartProc 0.005161535 s, TEndProc 18.073223256 s;
  durata processata **18.068061721 s**; VV.
- Frequenza processata: 9.372871761–10.086691452 GHz.
- SCPCOA a 9.036361296 s: incidence 21.842925233°, graze 68.157074767°,
  azimuth 101.919310567°, slant range 610,403.751 m, right-looking.
- SCP identico al CPHD. UUID e CollectionStart coincidono.

Le differenze geometriche CPHD/SICD sono coerenti con reference time diversi:
SICD SCPTime è 2.038888368 s prima del ReferenceTime CPHD.

## 9. Asse range/azimuth

Determinazione inequivocabile per questo file:

- Row = range = NumPy axis 0.
- Col = Doppler/azimuth = NumPy axis 1.
- Col.Sgn=-1: image-to-spectrum =
  `sarpy.processing.sicd.fft_base.fft_sicd(array, 1, sicd)`, equivalente a
  `numpy.fft.fft(axis=1)` in questo prodotto.
- Col.DeltaKCOAPoly=0: non serve deskew Col per questo prodotto.

La Col proiettata a terra ha bearing 191.246711°, quasi parallelo alla ground
track, ulteriore controllo geometrico indipendente.

## 10. Problemi scientifici/software

1. Il SICD usa soltanto l'80.1571% del dwell CPHD: non può generare un'apertura
   da 20 s. Il punto 20 s richiederà focalizzazione/rifocalizzazione dal CPHD.
2. Il prototipo inverte il segno/direzione fisica della FFT per questo metadata.
3. Il taglio azimutale pre-FFT del prototipo rende inaffidabile la decomposizione.
4. La finestra nativa è dichiarata `SVA`, ma mancano i campioni WgtFunct: non è
   possibile ricostruire esattamente il deweighting nativo.
5. Il SICD è XSD-valid, ma `sicd.is_valid(recursive=True)` è false: oltre alla
   WgtFunct mancante, SarPy 2.0.1 tratta erroneamente come incoerente il chirp a
   pendenza negativa. Con `abs(TxFMRate)` banda ed estremi coincidono esattamente.
6. La relazione fra frazione Doppler e tempo resta nominale. Non va presentata
   come tempo esatto finché non viene calibrata con CPHD/PVP.
7. Il GEC non è stato usato come ground truth né per misure d'onda.

## 11. Piano concreto per il primo test nominale da 6 s

1. Nel blocco 2 implementare e testare una libreria indipendente dai dati reali:
   FFT metadata-aware, finestre rect e Tukey, centri/overlap espliciti, guadagni
   ed ENBW, metadata JSON e tutti i cinque test sintetici richiesti.
2. Dopo i test, scaricare nel blocco 3 l'unico SICD verificato con resume,
   `--fail`, preflight, `.part`, controllo UUID e lunghezza finale. Dimensione
   11.48 GB, sotto la soglia di 20 GB.
3. Selezionare tre ROI riproducibili (nearshore, offshore, land) in JSON. Il GEC
   potrà aiutare soltanto a localizzarle; coordinate e proiezione saranno poi
   verificate sul SICD.
4. Leggere chunk di Row/range da 256 o 512 righe mantenendo tutte le 107,800
   colonne azimuth. Un chunk complex64 vale circa 221 o 442 MB. La ROI azimuth
   sarà ritagliata solo dopo IFFT.
5. Usare il supporto Col reale di 86,240 bin. Una finestra nominale da 6 s vale
   inizialmente frazione 6/18.068061721 = 0.332077679, circa 28,638 bin.
6. Formare tre look non sovrapposti centrati nel supporto, con centri temporali
   nominali circa 3.039, 9.039 e 15.039 s da CollectionStart. Le etichette saranno
   marcate `nominal/approximate`.
7. Eseguire sia rect sia Tukey, con normalizzazione ed ENBW registrati. Non si
   tenterà deweighting SVA non documentato.
8. Scrivere soltanto chip complex64 post-IFFT e diagnostiche PNG: full-aperture
   intensity, intensità dei look, differenze, finestre Doppler, coregistrazione e
   coerenza; nessun sub-look full-scene.
9. Usare terra per stimare shift/ramp deterministici prima di interpretare il
   mare. Bloccare qualunque interpretazione oceanografica se l'effetto compare
   anche su terra o non è stabile rispetto all'estensione azimuth.

Il dwell sweep resta escluso finché questo test non supera controlli di asse,
orientamento, fase, stabilità rispetto alla finestra spaziale e land control.

