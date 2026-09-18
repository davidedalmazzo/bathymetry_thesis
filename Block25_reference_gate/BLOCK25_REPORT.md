# Block 25 — rescreening dei 529 con i gate corretti

Data: 2026-09-15. Nessuna rete, nessun dato SAR. Solo `BLOCK21_ALL_CANDIDATES.csv`.
Produce una **coda di interrogazione** e lo script che la esegue; non scarica nulla.

## 1. Il gate sulla disponibilità pubblica non serviva

Applicato ai 529 `CONDITIONAL_REFERENCE_CHECK`:

```
CONDITIONAL_REFERENCE_CHECK                                529
+ prodotto complesso PUBBLICO (size non nulla)             527
  (contro has_sicd/has_cphd = True:                        529)
```

**Taglia 2 scene su 529.** Il candidato 2 del Block21 era un caso isolato, non un
difetto sistematico. La mia preoccupazione del Block24 era sovradimensionata:
la correzione al selettore resta giusta — `has_*` viene dallo STAC, la dimensione
dal listing pubblico — ma **non cambia la popolazione**. Va detto.

## 2. Il risultato strutturale: la ROI fissa un tetto sul periodo

Chiedere almeno 10 lunghezze d'onda nella finestra (`δL/L ≤ 0.1`) si inverte in
un **tetto sul periodo osservabile**:

| ROI | L massima | T massimo (acqua profonda) | n scene |
|---|---|---|---|
| 1500 m | 150 m | **9.80 s** | 167 |
| 1000 m | 100 m | **8.00 s** | 148 |
| 750 m | 75 m | 6.93 s | 116 |
| 500 m | 50 m | 5.66 s | 66 |
| 250 m | 25 m | 4.00 s | 30 |

**L'impronta Umbra non può risolvere spettralmente lo swell lungo.** Un'onda da
15.4 s (`L = 370 m`) in una ROI da 1500 m dà 4 lunghezze d'onda: è esattamente la
configurazione dei candidati 1, 2, 3 e 5 del Block21, ed è la stessa in cui
Romeiser ha dovuto tagliare a `L > 200 m`.

**Il Block21 ha selezionato le onde che le sue stesse ROI non sanno misurare.**
La preferenza per i periodi lunghi va rovesciata: il bersaglio corretto è
**T ≈ 6–10 s**, che è anche dove la rotazione di fase è buona su dwell di 5–15 s.

## 3. La coda

```
527 con complesso pubblico
+ stazione entro 10 km                                     148
+ ROI >= 1000 m                                            106
+ rotazione di fase utilizzabile al periodo risolvibile     99
```

Stazioni: 46256 (52), 44063 (18), 41118 (17), 44064 (3), 42087 (3), 44087 (2),
51202 (2), poi 46240, 51209, 41053, 46277, 44061, 46242, 46216, 41052, 44054
con una ciascuna.

Le più economiche con fase utilizzabile:

| scena | staz | km | ROI | dwell | T_max | Δφ@T_max | GB |
|---|---|---|---|---|---|---|---|
| 2023-09-17-01-34-01_UMBRA-04 | 44063 | 0.79 | 1500 | 3.0 s | 9.80 s | 72° | **0.24** |
| 2023-07-13-15-17-44_UMBRA-04 | 44063 | 2.90 | 1000 | 6.8 s | 8.00 s | 199° | 1.61 |
| 2024-01-14-16-04-15_UMBRA-08 | 41118 | 1.78 | 1000 | 6.2 s | 8.00 s | 181° | 2.65 |
| **2024-10-24-20-37-20_UMBRA-08** | **51202** | 6.93 | 1000 | **10.0 s** | 8.00 s | **292°** | **3.45** |
| 2024-02-13-01-46-35_UMBRA-04 | 42087 | 8.55 | 1500 | 7.0 s | 9.80 s | 167° | 3.48 |

## 4. Il sospetto che resta, e va verificato con la boa

Sondaggio GEBCO sui punti rappresentativi delle stazioni più promettenti:

| stazione | luogo | profondità |
|---|---|---|
| 51202 | Kaneohe, Oahu | **−5 m** |
| 41118 | dietro Cape Canaveral | **−5 m** |
| 44063 | Chesapeake | −17 m |
| 42087 | Tobago | **+8 m (terra)** |
| 51209 | Pago Pago, Samoa | **−51 m** |

Quattro su cinque sono in acqua riparata — laguna, lagoon dietro il reef,
estuario. È lo stesso meccanismo del Block24: **l'intersezione fra "scena Umbra"
e "boa entro 10 km" seleziona acqua riparata quasi per costruzione**, perché
Umbra riprende porti e le boe costiere stanno vicino a riva. E acqua riparata
significa `Hm0` piccolo, che è il gate che ha bocciato tutti e cinque i candidati
del Block21.

GEBCO a 460 m su lagune e reef è grossolano e i punti non sono i centri ROI
effettivi di ogni scena: è un **sospetto**, non una conclusione. **Solo `Hm0`
dalla boa lo risolve**, ed è precisamente ciò che lo script qui sotto va a
misurare.

Nota: **51209 (Pago Pago) a −51 m è l'unico in acqua aperta** del sondaggio, ed
è esposto allo swell del Pacifico meridionale. Una sola scena, dwell 3.6 s.

## 5. Consegna

- `BLOCK25_QUERY_QUEUE.csv` — le 99 scene con tutti i parametri offline.
- `run_block25_reference_gate.py` — interroga la boa per ciascuna e applica i due
  gate che mancano:
  - **G4** `Hm0 ≥ 1.5 m` — soglia **descrittiva, non calibrata**, ancorata al
    fatto che Vandenberg a 1.99 m era già marginale (Block15K Livello 2);
  - **G5** differenza assiale onda-range `≤ 35°`.
  
  Riusa `umbra_sar.reference_recovery` (Block17/18): stessa politica di
  completezza direzionale congiunta, stessa gestione dei missing, stesso budget.
  Una sola lettura di `time` per stazione, poi uno spettro per scena.
  Budget: 250 transazioni, 150 MiB.

Va eseguito sulla macchina dell'utente: né il container cloud né la workspace
locale raggiungono `dods.ndbc.noaa.gov` in questa sessione.

## 6. Cosa aspettarsi

Se l'esito è **zero candidati con `Hm0 ≥ 1.5 m`**, non è un fallimento dello
screening: è il risultato, e dice che l'archivio aperto Umbra non campiona la
combinazione «mare energico + boa vicina + ROI adeguata». A quel punto la
verifica della fase va fatta **senza boa**, con i bin in acqua profonda e il test
AIS già documentati in
`claude/validazione-senza-boa-bin-acqua-profonda-2026-09-15.md`.
