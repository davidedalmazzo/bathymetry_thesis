# Block 31 — Duck: 11 Staring Spotlight, e la conservazione di ω smette di essere un'ipotesi

Data: 2026-09-17. Fonti: export EOWEB (DLR) delle acquisizioni TerraSAR-X su Duck;
condizioni FRF recuperate via OPeNDAP. Nessun download SAR, nessuna inversione,
nessuna correzione di q.

---

## 1. Cosa c'è in archivio

EOWEB ha **20 acquisizioni TerraSAR-X** su Duck: 2 SpotLight (SL, 2 m),
7 High Resolution Spotlight (HS, 1 m) e **11 Staring Spotlight (ST, 0.24 m)**.

FedEO restituiva HTTP 500 sulla collezione ST: l'assenza era un guasto del
servizio, non dell'archivio. Conferma che un esito vuoto da un catalogo
federato non è una conclusione.

Le 11 ST: TSX-1 e TDX-1, 2020-09 → 2023-11, tutte HH, tutte con il molo FRF
nell'impronta, dwell **4.74–5.79 s**, Δφ a $T=10$\,s fra **111° e 135°**.
Gli identificativi terminano in `TSX-1.SAR.L0`: il **grezzo** è catalogato.

### Convenzione temporale di EOWEB, verificata

`span × velocità al suolo (7.03 km/s) = estensione azimutale della scena focalizzata`

| modo | span | → azimut | nominale |
|---|---|---|---|
| SL | 1.447–1.491 s | 10.18–10.48 km | 10 km |
| HS | 0.741–1.117 s | 5.21–7.85 km | 5 km |
| ST | 0.391–0.432 s | 2.75–3.04 km | 2.5–2.8 km |

Combacia su tutti e tre i modi. Lo span **non è né il dwell né il data take**,
ed è una convenzione *diversa* da CLEOS, dove i 7.9 s delle CSK erano il data
take. Due cataloghi, due convenzioni, entrambe scambiabili per dwell.

---

## 2. Il risultato che chiude Block 28

Block 28 si era fermato perché la conservazione di ω fra boa e ROI era
un'**ipotesi non falsificabile con una sola boa**. Con il transetto FRF
(8 m-array, awac-11m, waverider-17m, waverider-26m) si misura.

**Ma non su $T_p$.** $T_p$ è l'argmax di uno spettro a bin discreti: in mare
largo o bimodale salta fra bin e fra sistemi. Letto in secondi sembra variare
del 2–49% attraverso il transetto. Letto **in frequenza e confrontato con la
larghezza di bin** (Datawell/CDIP: ~0.005 Hz sotto 0.1 Hz, ~0.01 Hz sopra):

| istante | f_peak per strumento [Hz] | spread | in bin |
|---|---|---|---|
| **2020-12-09 23:00** | 0.0903 0.0900 0.0918 0.0915 | 0.0018 | **0.4** |
| **2020-10-08 11:15** | 0.1078 0.1060 0.1033 0.1083 | 0.0050 | **0.5** |
| **2020-09-07 22:51** | 0.1275 0.1292 0.1221 0.1215 | 0.0077 | **0.8** |
| 2023-11-06 22:51 | 0.1245 0.1210 0.1422 | 0.0212 | 2.1 |
| 2021-10-12 11:07 | 0.1088 0.1158 0.1163 0.0903 | 0.0261 | 2.6 |
| 2021-10-13 23:00 | 0.1047 0.1203 0.0945 0.0925 | 0.0278 | 2.8 |
| 2020-11-10 11:15 | 0.1352 0.1058 0.1066 0.1217 | 0.0295 | 2.9 |
| 2020-09-11 11:07 | 0.1390 0.1327 0.1178 0.1478 | 0.0299 | 3.0 |
| 2021-04-20 23:00 | 0.1170 0.1490 0.1118 0.1170 | 0.0372 | 3.7 |
| 2020-11-12 22:51 | 0.1867 0.1802 0.1857 0.1190 | 0.0677 | 6.8 |

**In tre istanti su dieci il picco è conservato entro un singolo bin spettrale
su tutto il transetto da 8 a 26 m.** Sono i casi in cui domina un solo sistema
stretto. Negli altri il picco salta fra sistemi: non falsifica la conservazione,
mostra che $T_p$ è la statistica sbagliata.

Questo è il risultato che serviva: la premessa centrale del metodo diventa
**osservata** dove è verificabile, invece di assunta. Va scritto in tesi così,
con l'avvertenza che lo shoaling ridistribuisce $E(f)$ e quindi **i momenti
spettrali cambiano legittimamente anche a ω esattamente conservata**.

**Prossimo passo naturale**: rifare il test su `waveEnergyDensity` invece che
su $T_p$, confrontando l'asse delle frequenze di una feature identificabile.
Il dataset FRF ha già gli spettri; non serve alcun dato nuovo.

---

## 3. Triage delle 11 ST

φ è l'angolo fra la direzione d'onda **misurata** alla boa a 17.8 m e la
direzione di range. Non assunto.

| acq_utc | Hs | Tp | φ | Δφ | margine | H/L | boa dentro | note |
|---|---|---|---|---|---|---|---|---|
| **2020-09-07 22:51:35** | 1.27 | 7.84 | **0.3°** | 141° | 137× | **0.0151** | **sì** | AUTO_APPROVED, inc 23.3° |
| **2023-11-06 22:51:53** | 0.92 | 8.03 | **0.4°** | 138° | 183× | 0.0106 | **sì** | AUTO_APPROVED, inc 23.3° |
| **2020-12-09 23:00:08** | 0.52 | 11.08 | **0.9°** | 119° | 293× | 0.0039 | **sì** | LIMITED_APPROVAL, swell stretto |
| 2020-11-10 11:15:43 | 0.83 | 7.39 | 7.8° | 154° | 7.5× | 0.0109 | no | |
| 2020-09-11 11:07:08 | 0.94 | 7.19 | 7.2° | 188° | 7.0× | 0.0128 | no | Δφ avvolge |
| 2021-04-20 23:00:07 | 0.64 | 8.55 | 27.1° | 154° | 4.3× | 0.0068 | no | |
| 2021-10-13 23:00:15 | 1.11 | 9.55 | 21.0° | 138° | 4.0× | 0.0101 | no | **COSMO 15 min prima**, DUNEX |
| 2020-10-08 11:15:42 | 0.50 | 9.28 | 58.3° | 123° | 3.5× | 0.0047 | no | |
| 2021-10-12 11:07:16 | 1.46 | 9.19 | 49.5° | 147° | 1.3× | 0.0140 | no | |
| 2020-11-12 22:51:36 | 1.28 | 5.36 | 20.7° | 207° | 0.8× | 0.0289 | no | Δφ avvolge, cut-off fallisce |
| 2021-01-21 11:07:06 | 0.46 | 6.68 | 26.7° | 203° | 3.2× | 0.0071 | no | boa 17 m stale (9.9 h) |

### Tre avvertenze sulla lettura

1. **I margini enormi non sono confrontabili fra loro.** `margine = L / (sin φ · λ_c)`
   diverge per φ → 0. Sotto ~5° satura: 137×, 183× e 293× dicono tutti la stessa
   cosa, cioè che la componente azimutale è trascurabile. Fra quelle tre a
   discriminare è la **ripidità**, non il margine.
2. **Δφ > 180° non squalifica.** Con un dwell di 4.7–5.8 s la base temporale si
   **sceglie**: basta scendere da 0.65 a ~0.45 del dwell. È una libertà che le
   CSK, con 1.4–1.9 s di dwell, non avevano.
3. **Le tre scene a φ < 1° sono le stesse tre che contengono la boa.** Non è
   fortuna: a Duck la direzione di range ascendente (79–80°T) coincide quasi con
   l'asse cross-shore del FRF, quindi con mare shore-normal φ → 0. È una
   proprietà sistematica del sito, e vale anche per il tasking futuro.

---

## 4. Raccomandazione

**Ordinare `2020-09-07 22:51:35`** (TDX-1, ST, ASC, spot_015, inc 23.25°,
AUTO_APPROVED, `XXXXB00000000555325955346`, livello **L0**).

È l'unica scena che tiene insieme tutto: onda a **0.3°** dal range, Δφ = 141°,
ripidità 0.0151 — la migliore fra quelle a geometria perfetta — boa a 17.8 m
**dentro** l'impronta, frequenza conservata entro 0.8 bin su tutto il transetto,
e incidenza 23°, cioè il NRCS migliore possibile per una HH sul mare.

**Seconda**: `2023-11-06 22:51:53` — stesso fascio, stessa geometria, ripidità
0.0106, la migliore consistenza direzionale fra strumenti (spread 2.6°).

**Terza, per la coppia controllata**: `2021-10-13 23:00:15`, con la CSK delle
22:45:03 a 15 minuti e DUNEX in corso. φ = 21°, Δφ = 138°, margine 4×. Vale
non per la qualità assoluta ma perché è un **esperimento controllato**: due
sensori sullo stesso mare, uno in pieno regime e uno al limite.

`2020-12-09` ha lo swell più pulito dell'intero archivio (frequenza conservata
a 0.4 bin) ma ripidità 0.0039: modulazione di tilt debolissima. È il
compromesso classico — il mare più pulito è anche il meno visibile al radar —
e per questo non è la prima scelta, nonostante il margine di 293×.

## 5. Cosa resta non verificato

- Rapporto `Δφ/σ_Δφ` a Δt ≈ 1 s (regime CSK) e ≈ 3.6 s (regime ST): il test
  sulla catena sintetica esistente non è ancora stato girato.
- Conservazione di ω su `waveEnergyDensity` invece che su $T_p$.
- Se il prodotto L0 esponga i parametri di steering necessari a datare i
  sub-look, e come vari il dwell attraverso la scena in azimut.
- Ordinabilità effettiva delle due scene `LIMITED_APPROVAL`.
- Pulizia del campo d'onda nella singola acquisizione (nessuna analisi AIS).
- Asse cross-shore FRF a 70°T: resta stimato. Le direzioni misurate
  (79–81°T con mare shore-normal) suggeriscono che la normale vera sia più
  vicina a 79° che a 70°. Da confermare sui metadati FRF.
