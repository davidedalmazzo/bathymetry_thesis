# CHECKPOINT 18 — recupero per-bin e rivalutazione dei quattro riferimenti

## Esito

Sono stati recuperati e normalizzati **4 riferimenti su 4**. Tutti appartengono
alla stazione NDBC 42084, sono entro 34,164 km e hanno offset rispettivamente
`+25,9`, `+1359,4`, `+33,4` e `−55,5 s`, quindi entro i limiti congelati di
50 km e 3600 s. La copertura della densità e la copertura energetica dei cinque
campi congiunti nella banda 0,04–0,25 Hz sono entrambe 1,0 per tutti i casi.
Sono quindi **4/4 riferimenti misurati ammissibili** secondo la politica Block17.

Questo non dimostra rappresentatività idrodinamica locale: la boa dista circa
34 km, e i momenti direzionali non determinano univocamente uno spettro 2-D.

## Provenienza e identità

Il dataset aggregato corrente espone dinamicamente 41.607 tempi e 98 frequenze.
Gli indici correnti coincidono con quelli storici e il vettore `time` restituisce
esattamente le quattro osservazioni attese.

Un audit successivo del manifest Block16A ha localizzato i quattro payload
originali già presenti in `Block8_validation/buoy_data`. La ricerca iniziale per
testo/hash non li aveva individuati; questo limite operativo è conservato nel
record, non nascosto. Le quattro risposte remote autorizzate hanno hash identico
agli originali locali e agli hash storici Block16A: si tratta di identità
byte-per-byte, non solo equivalenza numerica.

Sono state utilizzate 7 transazioni HTTP senza retry: DDS, DAS, coordinata time
e quattro subset. Totale 560.916 byte; massimo singolo 499.416 byte. Non sono
stati interrogati archivi annuali o CDIP perché aggregato, timestamp e payload
erano già completi. Nessun server ha ignorato il subset.

## Normalizzazione

Ogni riga per-bin conserva frequenza, larghezza ricostruita, densità, α1, α2,
r1, r2, cinque maschere individuali e maschera congiunta. Dal DAS effettivo:

- densità: `(meter * meter)/Hz`, `_FillValue=999`;
- α1/α2: `degrees_true`, `_FillValue=999`;
- r1/r2: adimensionali, `_FillValue=999`.

Il codice applica il missing separatamente per variabile: `99°` resta una
direzione valida. Frequenze positive, strettamente crescenti, senza duplicati;
dimensioni coerenti. La documentazione NDBC definisce α1/α2 come direzioni
**from** rispetto al nord vero e la conversione di propagazione è `(from+180)
mod 360` ([NDBC measurement descriptions](https://www.ndbc.noaa.gov/faq/measdes.shtml)).

Il prodotto OPeNDAP non espone bordi o una variabile bandwidth. Le larghezze
sono quindi ricostruite dai punti medi tra centri e dichiarate come tali. NDBC
prescrive l'integrazione `Σ S(f)d(f)` e documenta che griglia e numero di bande
possono variare ([wave-height calculation](https://www.ndbc.noaa.gov/faq/wavecalc.shtml),
[raw spectral format](https://www.ndbc.noaa.gov/data_spec.shtml)). La tabella
NDBC standard delle bande non copre esplicitamente questa griglia a 98 bin;
non viene rivendicata falsa equivalenza con una bandwidth ufficiale.

## Metriche rispetto a Block16A

Hm0, frequenza/periodo del massimo, direzioni e momenti al massimo sono identici
(al più `5,6×10⁻17` per roundoff). L'unica differenza non nulla è la frazione
`f≤0,1 Hz` della scena del 14 marzo 2026:

- Block16A, trapezio: `0,00140647`;
- Block18, somma per bande: `0,00187529`;
- differenza: `+0,000468823`.

È un effetto del metodo d'integrazione, non di una revisione remota. Rimane molto
sotto il gate energetico storico 0,5 e non cambia alcun esito. I conteggi 6, 5,
3 e 7 sono riportati soltanto come `spectral_local_maxima_count`, mai come numero
di sistemi fisici. Non è stato applicato MEM.

## Rivalutazione delle scene

| Acquisition key | Storica | Block18 | Motivo residuo |
|---|:---:|:---:|---|
| `2e7cb…79dd` | D | D | swell non dominante; angolo range sfavorevole |
| `98fe2…13a0` | D | D | swell non dominante; angolo sfavorevole; mare debole |
| `9caef…1e9f` | D | D | swell non dominante; angolo range sfavorevole |
| `ae8a3…cf1` | C | C | swell misurato non dominante |

La completezza del riferimento è confermata, ma non rimuove i gate fisici.
Per tutte restano non verificate: `delta_eff`, clearance interna alla scala SAR,
separabilità del lobo, ROI di intensità utilizzabile, SNR/coerenza e mapping
Doppler–slow-time completo. CPHD dwell e SICD processed aperture restano colonne
distinte. La tabella gate-per-gate è in
`BLOCK18_CANDIDATE_GATE_COMPARISON.csv`.

## Riproducibilità e arresto

Il reparsing offline dei quattro payload riproduce 392 righe per-bin e tutte le
metriche con differenza massima zero. I payload originali, le risposte remote,
gli attributi, gli URL, gli errori/tentativi e gli hash sono nel manifest.
Vandenberg e i blocchi congelati non sono stati modificati; nessun dato SAR è
stato scaricato o letto.

Il solo prossimo passo motivato è rivalutare la **rappresentatività spaziale**
della boa 42084 per queste quattro scene tramite metadati oceanografici locali
indipendenti e già piccoli, prima di considerare qualsiasi prodotto SAR. Questo
passo non è avviato automaticamente.

