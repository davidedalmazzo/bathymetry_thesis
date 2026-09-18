# Block 27 — la corrente si cancella: la query si riordina sulla pulizia

Data: 2026-09-16. Corregge il Block26. Nessuna rete, nessun dato SAR.

## Hai ragione, e il Block26 sbagliava

**Una boa ormeggiata campiona l'elevazione in un punto fisso nel riferimento
terrestre: misura la frequenza assoluta `ω = σ + k·U`.** La fase del
cross-spettro fra sotto-look segue l'evoluzione del pattern nello **stesso
riferimento terrestre** — il pattern avanza con `c_abs = ω/k` — quindi
restituisce la stessa `ω`.

**Una corrente sposta le due misure in modo identico e si cancella nel
confronto.** Ordinare la coda per «rischio di corrente» era sbagliato.

C'è di più, e rafforza il punto: `ω` assoluta **si conserva lungo un raggio in
un mezzo stazionario**. Quindi nemmeno un campo di corrente spazialmente
disomogeneo rompe il trasferimento boa → scena, purché il mare sia lo stesso
sistema e le condizioni siano stazionarie.

È esattamente l'osservazione del Block14 («stiamo misurando la frequenza
assoluta, non quella intrinseca»), applicata nella direzione giusta.

### Dove la corrente conterebbe ancora

1. **Se servisse `σ`** per invertire la dispersione — cioè per la batimetria,
   che qui non interessa.
2. **Non stazionarietà** sull'offset temporale SAR–boa: una marea che cambia in
   ore, valutata su ~30 min, è un effetto piccolo.
3. **Gradienti così forti da cambiare il mare** fra boa e ROI — bloccaggio e
   rifrazione su una barra di marea. Ma questo non è un problema di riferimento:
   è un problema di **pulizia**, ed è così che va classificato.

## Il criterio corretto è la pulizia del campo d'onda

Non «corrente» ma: il mare nella ROI è un sistema singolo, pulito, e la boa lo
rappresenta? I rischi reali:

- **pennacchio fluviale** — fronti di sedimento e slick smorzano le onde di
  Bragg e producono struttura d'immagine spuria;
- **scie di navi** — sono **esattamente** i *«non-ocean-wave contributions at
  the same wavenumbers as ocean wave signatures of interest»* che il poster AGU
  2020 di Romeiser indica come causa del bias di frequenza. Per una misura di
  fase è un rischio di prim'ordine;
- **infrastrutture** — piattaforme offshore, doppie riflessioni;
- **bacino chiuso / fetch limitato** — mare confuso, spettro largo, nessun lobo
  netto;
- **gradienti di corrente forti** (barre, bocche di baia) — il mare alla boa non
  è quello nella ROI.

E il tuo punto sul delta del fiume è corretto: **il Golfo del Messico a
29.0 N / 90.0 W è la foce del Mississippi**, con pennacchio, sedimento, rotta
commerciale e piattaforme. Era in testa al Block26 solo perché avevo classificato
il rischio nel modo sbagliato.

## La coda riordinata

Popolazione allargata a `ocean_fraction ≥ 0.80` (era 0.99): **55 scene**.

| # | scena | staz | km | dwell | ocean | h | asse range | GB | sito |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2025-03-31-21-51-37_UMBRA-09 | 51209 | 6.93 | 3.6 s | 0.816 | −46 m | 240.3° | **2.55** | Tutuila, Samoa Americane |
| 2 | 2024-02-14-01-22-39_UMBRA-04 | 42087 | 8.27 | 5.0 s | 0.852 | −14 m | 300.2° | 3.09 | Tobago SW |
| 3 | 2024-02-13-01-46-35_UMBRA-04 | 42087 | 8.55 | 7.0 s | 0.810 | −14 m | 53.7° | 3.48 | Tobago SW |
| **4** | **2025-03-22-02-27-54_UMBRA-08** | **41052** | **8.75** | **13.6 s** | **0.996** | −19 m | 292.0° | 8.69 | **Sud di St. John, Isole Vergini** |
| 5 | 2024-02-14-14-24-58_UMBRA-07 | 42087 | 8.98 | 6.8 s | 0.919 | −14 m | 260.3° | 4.45 | Tobago SW |
| 6–23 | cluster 42094 | 42094 | 13.08 | 5.4–17.0 s | 1.000 | −24 m | varie | 9.5–17.0 | Golfo, delta del Mississippi |
| 24+ | Chesapeake, Hampton Roads, Long Island Sound, New York, SF Bar | | | | | | | | estuari e porti |

**I primi cinque sono tutti acqua pulita e aperta, con la boa fra 6.9 e 9.0 km,
e costano da 2.55 a 8.69 GB — meno del Golfo (12–17 GB).**

### Il migliore sulla combinazione: #4, Isole Vergini

`2025-03-22-02-27-54_UMBRA-08`, stazione 41052 (sud di St. John) a **8.75 km**,
`ocean_fraction = 0.996`, ROI 1500 m, **dwell 13.6 s** — il più lungo fra i siti
puliti — incidenza 28.1°, SICD 8.69 GB. Caraibi: acqua limpida, traffico basso,
nessun pennacchio, ed esposizione allo swell atlantico da N/NE, che a marzo è in
stagione.

L'unico dubbio è geometrico: GEBCO a 460 m sul centro ROI legge terra, perché la
griglia non risolve St. John. `ocean_fraction = 0.996` e `coast_distance =
2435 m` dicono che la ROI è al largo, ma **va confermato sull'impronta reale**.

### Il più aperto: #1, Samoa Americane

`−46 m` al centro ROI, Pacifico meridionale, traffico minimo. Ma `dwell 3.6 s` e
una sola epoca disponibile.

## Che cosa decide fra i primi cinque

Solo la boa, e sono tre numeri: **allineamento onda-range**, **ripidità `H/L`**,
**rotazione di fase**. Sono 4 stazioni e 55 scene: una query piccola.

`run_block27_frequency_query.py` — invariato nei gate rispetto al Block26
(assiale ≤ 35°, `H/L ≥ 0.010`, ≥ 3 λ nella ROI, fase 45°–1080°) ma con
l'ordinamento finale su **pulizia → allineamento → ripidità**, e senza la
classificazione per corrente.

La colonna `cleanliness_rank` della coda è un **giudizio dichiarato** sul corpo
d'acqua (pennacchio, traffico, bacino, esposizione), non una grandezza estratta
dai metadati. È scritta per essere contestata.
