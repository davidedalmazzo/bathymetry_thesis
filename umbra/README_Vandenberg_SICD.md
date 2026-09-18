# Vandenberg — SICD e decomposizione in sub-aperture

Acquisizione: `2025-02-16-18-55-44_UMBRA-10`.

## 1. Scaricare il SICD

Copia `download_vandenberg_sicd.bat` sul PC e avvialo. Scarica nella cartella:

`D:\Dati Tesi\Umbra\Vandenberg`

Il download usa `curl -C -`, quindi è riprendibile.

In alternativa, da Prompt di Anaconda:

```bat
cd /d "D:\Dati Tesi\Umbra\Vandenberg"
curl.exe -L -C - --retry 10 --retry-all-errors -o "2025-02-16-18-55-44_UMBRA-10_SICD.nitf" "https://umbra-open-data-catalog.s3.us-west-2.amazonaws.com/sar-data/task-data/f2f8c71e-6aec-4358-acda-93c5e68e8b4b/2025-02-16-18-55-44_UMBRA-10/2025-02-16-18-55-44_UMBRA-10_SICD.nitf"
```

## 2. Installare SarPy

Usa lo stesso Python con cui lancerai lo script:

```bat
python -m pip install sarpy numpy matplotlib
```

Poi verifica quale interprete stai usando:

```bat
where python
python -c "import sys, sarpy; print(sys.executable); print(sarpy.__file__)"
```

## 3. Verifica numerica dello splitter

```bat
python sicd_subaperture.py --self-test
```

Deve terminare con `SELF-TEST OK`.

## 4. Leggere il metadata vero del SICD

```bat
python sicd_subaperture.py "D:\Dati Tesi\Umbra\Vandenberg\2025-02-16-18-55-44_UMBRA-10_SICD.nitf" --inspect
```

Prima di processare, salva l'output. Controlliamo in particolare:

- `Grid.Type`;
- `ImageFormAlgo`;
- `Row.SS`, `Col.SS`;
- `TStartProc/TEndProc`;
- `CollectDuration`;
- `asse sub-aperture`;
- percentuale del supporto Doppler.

Per `Grid.Type = RGAZIM`, SICD definisce Row come range e Col come Doppler/azimuth, quindi lo script divide l'asse 1.

## 5. Primo esperimento consigliato: 6 s

Non partire subito con 2×2 km. Prima usa 1×1 km attorno allo SCP:

```bat
python sicd_subaperture.py "D:\Dati Tesi\Umbra\Vandenberg\2025-02-16-18-55-44_UMBRA-10_SICD.nitf" --mode tiled --dwell 6 --roi-size-m 1000 --outdir "D:\Dati Tesi\Umbra\Vandenberg\subap_6s_test"
```

Con un dwell completo di circa 22.6 s ci aspettiamo 3 sub-aperture non sovrapposte da circa 6 s.

Output principali:

- `roi_full.npy`: immagine complessa a piena apertura;
- `sub_6s_tiled_*.npy`: sub-look complessi;
- PNG omonime: solo quicklook;
- `subapertures.csv`: posizione di ogni sotto-banda e tempo centrale approssimato;
- `run_metadata.json`: parametri della decomposizione.

Per il cross-spettro si usano i `.npy`, non le PNG.

## 6. Curva di degradazione del dwell

Dopo aver verificato il test da 6 s:

```bat
python sicd_subaperture.py "D:\Dati Tesi\Umbra\Vandenberg\2025-02-16-18-55-44_UMBRA-10_SICD.nitf" --mode centered --dwells 20,16,12,10,8,6,5 --roi-size-m 1000 --outdir "D:\Dati Tesi\Umbra\Vandenberg\dwell_sweep"
```

Questo produce una sub-apertura centrale per ogni durata, utile a isolare l'effetto del dwell senza cambiare scena.

## 7. Limite metodologico da ricordare

La conversione fra frazione di banda Doppler e durata è inizialmente assunta lineare. È adatta a un primo test dello stimatore. Per il risultato finale della tesi, il centro temporale dei sub-look va ricostruito dal CPHD/PVP (TxTime / geometria di fase), non dalla semplice interpolazione lineare salvata nel CSV.
