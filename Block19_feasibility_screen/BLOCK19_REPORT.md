# Block 19 (ESPLORATIVO) — screen di fattibilità fisica congiunta

Data: 2026-09-15. Nessun prodotto SAR letto o scaricato. Nessuna scena promossa.
**Non introduce gate**: ordina e dichiara. Vandenberg resta congelato (Block15K).

## Perché

Tutti i gate dal Block16A al Block18 usano metadati d'onda e geometria e li
valutano **uno alla volta**. Nessuno usa la profondità. Il Block18 ha mostrato
che il percorso dei riferimenti è ormai corretto e che i quattro candidati
misurati falliscono su gate *fisici*. Questo blocco aggiunge la batimetria e
valuta i requisiti **in congiunzione**.

## Gate

| | requisito | forma |
|---|---|---|
| G1 | l'onda sente il fondo | `kh ≤ 1.5`, `A = 1 + sinh(2kh)/(2kh)` |
| G2 | batte il cut-off azimutale | `L/sin(φ) ≥ λ_c = 2π β σ_ur` |
| G3 | il dwell copre un ciclo | `T_dwell/T ≥ 1` |
| G4 | fondale dolce | il termine spaziale scala come `√∇h` |

**Correzione a quanto avevo affermato sul Block18.** Il cut-off azimutale agisce
sulla componente **azimutale** di `k`, non su `|k|`: un'onda che viaggia lungo
range non ne è mai tagliata. `φ_max` qui sotto è la libertà geometrica residua.
Applicato correttamente alla scena del Golfo del Messico (onda a 2.33° da range,
lunghezza apparente in azimut 695 m), **il cut-off passa**: la mia affermazione
precedente che fosse "sotto il cut-off di un fattore 3–8" era sbagliata. Quella
scena muore sul solo G1 — `kh = 4.44`, `A = 404` — che basta e avanza.

## Funnel del catalogo

10 140 acquisizioni → 5 333 con geometria valutata → **1 726 con un punto
oceanico** → 1 044 con CPHD → 384 con ROI ≥ 1500 m e costa ≤ 25 km → **125 con
dwell ≥ 10 s** → 57 località uniche.

Distribuzione: Pacifico 39, NE Atlantico 22, Golfo/Caraibi 17, Indiano 16,
Polare 15, NW Atlantico 9, **Mediterraneo 6**.

Le località dominanti sono porti e chokepoint — Jeddah (15 scene), Kivalina (12),
Southwest Pass (12), Singapore (9+5), Long Beach (5), Gibilterra (4), Hormuz,
Houston. Il tasking commerciale di Umbra non punta su coste aperte in shoaling.

## Risultati (GEBCO2020, stencil a 5 punti; T e Hs climatologici per costa)

| sito | h [m] | ∇h | Hs | Tp | kh | A | L | λ_c | φ_max | cicli | δh/h~ |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Vandenberg CA | 30 | 8.4e-3 | 2.0 | 13.0 | 0.96 | 2.7 | 196 | 66 | 90° | 1.73 | 38.8% |
| Santa Barbara CA | 22 | 1.1e-2 | 2.0 | 14.0 | 0.73 | 2.4 | 190 | 61 | 90° | 0.93 | 47.7% |
| Ventura CA | 13 | 7.5e-3 | 2.0 | 14.0 | 0.54 | 2.2 | 151 | 61 | 90° | 0.86 | 43.8% |
| Charleston SC | 15 | 6.0e-3 | 1.5 | 11.0 | 0.77 | 2.4 | 122 | 59 | 90° | 1.09 | 34.6% |
| Fukushima JP | 14 | 1.4e-2 | 2.0 | 12.0 | 0.67 | 2.3 | 131 | 71 | 90° | 1.00 | 55.3% |
| **Lord Howe (Tasman)** | 39 | **1.5e-3** | 2.5 | 13.0 | 1.14 | 3.1 | 215 | 82 | 90° | 0.92 | **16.1%** |
| Golfo del Messico | 20 | 1.0e-3 | 1.0 | 4.26 | **4.44** | **404** | 28 | 101 | 16° | 4.04 | 75.6% |

Il gradiente di Vandenberg ricavato qui dallo stencil GEBCO, 8.4e-3, riproduce
il valore congelato 8.79e-3: controllo di sanità superato.

**Lord Howe Island** è il miglior sito del catalogo: `∇h = 1.5e-3`, `h = 39 m`,
swell del Tasman. Manca solo il dwell (0.92 cicli sul dwell nominale).

## Italia

Batimetria GEBCO su stencil ±0.10°/±0.15°. Periodi: relazione `Tp = 5.53·Hs^0.34`
per l'Adriatico (Water 2022, 14, 2678) e boa RON Alghero per la Sardegna
occidentale (Tp max misurato 12.1 s, tempeste ~11 s, Hs max 6.65 m).

| sito | h [m] | ∇h | Hs | Tp | kh | A | L | λ_c | φ_max | δh/h~ |
|---|---|---|---|---|---|---|---|---|---|---|
| **Alto Adriatico / Venezia** | 23 | **4.1e-4** | 4.0 | 8.9 | 1.34 | 3.7 | 108 | 193 | 34° | **8.4%** |
| **Alto Adriatico / Venezia** | 23 | 4.1e-4 | 5.0 | 9.6 | 1.20 | 3.3 | 120 | 223 | 32° | 8.4% |
| **Ravenna / Rimini** | 13 | **4.5e-4** | 3.0 | 8.0 | 1.05 | 2.9 | 78 | 161 | 29° | **8.9%** |
| Ravenna / Rimini | 13 | 4.5e-4 | 5.0 | 9.6 | 0.83 | 2.5 | 98 | 223 | 26° | 9.3% |
| W Sardegna / Oristano | 41 | 2.3e-3 | 6.7 | 12.1 | 1.31 | 3.6 | 197 | 237 | 56° | 19.9% |
| W Sardegna 20 m | 20 | 2.3e-3 | 4.0 | 11.0 | 0.92 | 2.7 | 137 | 156 | 61° | 20.5% |
| W Sardegna, decadimento | 20 | 2.3e-3 | 2.5 | 11.0 | 0.92 | 2.7 | 137 | 97 | **90°** | 20.5% |

Scartati: Golfo di Taranto (−805 m al punto campionato, scende a −1172 m
in 15 km), Sicilia meridionale (da −24 a −154 m in 11 km), Tirreno in generale
(piattaforma stretta).

## Lettura

1. **L'alto Adriatico ha l'indicatore migliore di tutto il confronto**, 8.4–9.3%,
   contro 16% di Lord Howe e 39% di Vandenberg. Domina `∇h ≈ 4e-4` (1:2400).
2. **Non serve una swell vera.** Con `h = 13–23 m` una comune tempesta di
   scirocco o bora (`Hs = 3–5 m`, `Tp = 8–9.6 s`) dà già `kh = 0.83–1.34`,
   dentro la banda usabile. Il periodo lungo serve solo dove il fondale è
   profondo.
3. **Il vincolo adriatico è il cut-off, ed è geometrico, non climatico.** Serve
   che l'onda stia entro ~26–34° dall'asse range. In Adriatico la direzione è
   prevedibile (scirocco lungo l'asse verso NW), quindi è pianificabile in
   tasking.
4. **La Sardegna occidentale è l'unica costa italiana con una swell vera**
   (Tp 12.1 s misurati ad Alghero) ma il fondale è 5× più ripido: δh/h ~ 20%.
   La finestra migliore è il **decadimento** del maestrale, quando Tp resta
   11–12 s mentre Hs cala a 2.5–4 m: lì `λ_c` crolla e `φ_max` arriva a 90°.
5. **Nel Mediterraneo periodo e altezza sono accoppiati** dalla `Tp = 5.53·Hs^0.34`:
   per allungare il periodo serve una tempesta più grande, che alza `σ_ur` e
   quindi `λ_c`. È il motivo per cui il cut-off morde proprio negli eventi che
   servirebbero. Solo la fase di decadimento rompe l'accoppiamento.

## Limiti dichiarati

- GEBCO2020 è a 15 arcsec (~460 m); i gradienti sono regionali, non locali.
- `Tp` e `Hs` sono **climatologici per costa**, non dello scene: per una scena
  vera vanno presi dal modello/boa all'ora dell'acquisizione.
- `λ_c` usa `σ_ur` dal solo picco spettrale: è un limite inferiore, la coda
  allarga il cut-off. Conservativo nel verso giusto.
- `δh/h` è un **indicatore** sotto le ipotesi di `docs/NOTE_accuracy_envelope_open.md`:
  la covarianza `k`–`ω` non è trattata e `2π/W` è una risoluzione, non l'errore
  di uno stimatore. **Non è una soglia e non ordina da solo.**
- Le 7 scene italiane presenti in catalogo hanno tutte `dwell ≤ 7.8 s`: le righe
  italiane qui sopra usano un dwell ipotetico di 22 s. **L'Italia è un bersaglio
  da tasking, non una scena trovabile nell'archivio aperto.**

## File

`code/analyze_block19_feasibility_screen.py`, `BLOCK19_SCREEN.json`,
`BLOCK19_REPORT.md`.
