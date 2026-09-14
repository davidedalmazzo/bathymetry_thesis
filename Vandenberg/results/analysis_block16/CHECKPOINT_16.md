# Checkpoint 16 — Il riferimento della boa non ha due componenti, e non ne ha mai avute

Data: 2026-09-14. Nessuna formazione, nessun download, nessuna inversione.
Solo il prodotto spettrale della boa 46218 gia' su disco dal Block 5.
**Questo blocco non riapre Vandenberg**, congelato dal Block 15K: corregge il
riferimento esterno contro cui i Block 13–15 erano stati scritti.

## Domanda

«Siamo sicuri di come computiamo lo spettro del mare dalla boa? Mi sembra
strano avere solo un picco.» L'istinto era corretto ma puntava nella direzione
opposta: il problema non e' che il picco sia uno, e' che i Block 13 e 15 ne
avevano dichiarati **due** che non esistono.

## Il calcolo e' corretto

`analyze_block5_ndbc_spectrum.py` ricava le larghezze di banda dai bordi
(`np.diff(edges)`), non da un passo costante. Verifica esatta:
`sum(E*bw - var) = 0.0`. Ne seguono `m0 = 0.246774 m²` e `Hm0 = 1.9871 m`.
Le 64 bande 0.025–0.58 Hz con larghezze {0.005, 0.0055, 0.0075, 0.0095, 0.01}
corrispondono al formato CDIP per boe direzionali, non al WPM NDBC a 47 bande.
La 46218 e' una Datawell gestita CDIP: CDIP **decodifica** lo spettro calcolato
a bordo, non lo ricalcola. Nessun errore da correggere in questa parte.

## Reperto 1 — la bimodalita' in frequenza non esiste

DOF equivalenti stimati dalla dispersione attorno alla media mobile a 3 bande:
`nu >= 17` (limite inferiore: la curvatura spettrale reale gonfia il residuo).
Compatibile con i 33 documentati da NDBC per il sistema DACT WA.

Test F bilaterale sulla «valle» a 14.29 s che separerebbe i due picchi:

| nu | E(13.33)/E(14.29) | p | E(15.38)/E(14.29) | p |
|---|---|---|---|---|
| 17 | 1.493 | **0.42** | 1.373 | **0.53** |
| 28 | 1.493 | 0.30 | 1.373 | 0.41 |
| 33 | 1.493 | 0.26 | 1.373 | 0.37 |

Non significativo a nessun `nu` plausibile. E su uno spettro liscio la
probabilita' che il centrale di tre bin sia il minimo e' 1/3: sui 18 bin interni
della banda ce ne si aspettano **6** di valli spurie. Osservarne una non e'
evidenza di nulla.

## Reperto 2 — nemmeno la bimodalita' direzionale

Uno spettro 1-D e' un collasso su theta: due sistemi da direzioni diverse
possono condividere la banda. Ricostruito con il metodo di massima entropia di
Lygre & Krogstad (1986), quello che CDIP stesso distribuisce, il marginale
direzionale della banda mostra **due lobi**, a 72.5° e 102.5° di propagazione.

**E' un artefatto.** Controllo decisivo: presi i momenti **esatti** di una
distribuzione `cos^{2s}(theta/2)` **unimodale per costruzione**, spinti nello
stesso codice MEM, l'uscita ha due lobi per **ogni** s da 1 a 20. A s = 20 i
lobi escono a **72.5° e 107.5°** — cioe' esattamente la coppia trovata nel dato.

Seconda conferma, indipendente dal MEM: l'`r2` osservato **supera** quello di
una `cos^{2s}` unimodale con lo stesso `r1` in **tutte** le bande
(0.570 vs 0.445, 0.750 vs 0.716, 0.360 vs 0.264, ...). Una distribuzione con
`r2` piu' alto del modello unimodale e' **piu' stretta**, non bimodale. E
`alpha1 − alpha2` sta entro 4° in sette bande su dieci.

Terza: il conteggio dei lobi MEM salta 1, 2, 1, 2 da un bin al successivo su uno
stato di mare fisicamente liscio. Instabilita', non struttura.

## Che cosa c'e' davvero

**Un solo sistema, largo.** Banda 0.055–0.115 Hz, 57.1% di m0:

- media pesata f = 0.08377 Hz, **T = 11.94 s**; picco della lisciata 14.11 s
- `sigma_f` = 0.01481 Hz, **larghezza relativa eps = 0.177**
- `omega` = 0.5264 ± 0.0930 rad/s
- direzione media di propagazione 89.7°, `1 − R` = 0.0145, `r1` medio 0.848,
  cioe' uno spread di circa 32°

Dentro il cono `±20°` attorno al vettore d'onda immagine (bearing 79.84°) c'e'
il 42.6% dell'energia di banda, con `omega` = 0.5168 ± 0.0934 rad/s.

## Conseguenze sui documenti congelati

1. **Non esiste la coppia 13.33 / 15.38 s.** Il Block 13
   (`block13-spettro-boa-componente`) e il CHECKPOINT_15 la trattano come due
   componenti co-dominanti. Va letta come **due bin adiacenti dello stesso
   sistema**, separati da rumore chi-quadro.
2. **Il criterio di selezione del CHECKPOINT_15 e' auto-incoerente.** Chiedeva
   `d_omega * T_dwell > 2*pi`; applicato allo spettro che lo ha motivato,
   **nessuna** coppia arriva a un ciclo di battimento: 13.33/15.38 → 0.218,
   10.53/14.29 → 0.546, 10.27/14.48 → **0.618**, la migliore in assoluto
   10.53/16.67 → 0.764. La coppia 10.27/14.48 raccomandata dal CP15 **fallisce
   il criterio sotto cui era stata proposta**, e per di piu' non corrisponde a
   bande della boa: viene dalla finestra scorrevole SAR del Block 13 e non e'
   mai stata corroborata.
3. **L'inversione logica del CP15 era un errore di categoria.** «Swell stretto =
   non identificabile» confonde «non so dire se sono una o due» con «la misura
   e' sbagliata». Se il sistema e' stretto le due ipotesi restituiscono la
   stessa `omega` entro la larghezza di banda: non c'e' niente da separare.

## Reperto 3 — lo stimatore non e' distorto, e' solo largo

Sistema singolo di larghezza relativa `eps`, tempi di look uniformi sullo span
misurato (i centri veri del Block 11 deviano < 1%), 800 realizzazioni:

| eps | mediana omega | p10–p90 | larghezza 80% rel. | mediana R² |
|---|---|---|---|---|
| 0.03 | 0.5267 | 0.5125–0.5409 | 0.054 | 1.0000 |
| 0.08 | 0.5270 | 0.4821–0.5715 | 0.170 | 1.0000 |
| 0.177 | 0.5262 | 0.4339–0.6257 | 0.365 | 0.9991 |
| 0.25 | 0.5306 | 0.4009–0.6535 | 0.476 | 0.9973 |

**Mediana invariata a ogni larghezza.** L'allargamento allarga, non sposta —
stessa asimmetria gia' vista nel Block 15a col rumore. E **R² >= 0.997 fino a
eps = 0.25**: la conclusione del CP15 che R² non ha potere diagnostico si
generalizza a ogni larghezza di banda, non solo alle miscele a due righe.

Collocazione del valore congelato 0.41207 rad/s nella legge a sistema singolo
con eps = 0.177: **7.6° percentile** (mediana 0.5276, p10–p90 0.4276–0.6311).
Estrazione bassa di una distribuzione larga. Riportato come collocazione, non
come validazione: Vandenberg resta alla classificazione del Block 15K.

## Reperto 4 — il collo di bottiglia non e' omega

Scegliendo `W` il piu' largo possibile purche' lo smear da shoaling del picco
resti dentro un elemento di risoluzione (oltre, la finestra risolve piu' fine di
quanto il picco sia stretto e viola la 2.36), con T = 13 s:

| `grad h` | h = 10 m | h = 25 m | h = 40 m |
|---|---|---|---|
| 8.79e-3 (Vandenberg) | 51.4% | 41.8% | 39.8% |
| 2e-3 | 23.4% | 19.6% | 18.7% |
| 1e-3 | 16.6% | 13.8% | 13.2% |
| 5e-4 | 11.7% | 9.7% | 9.3% |

(`dh/h` dal **solo** termine spaziale `A * dL/L`, con `omega` esatta.)

Su Vandenberg il pavimento e' **40–62%** comunque si misuri `omega`. Il vincolo
che lega il metodo e' la **risoluzione in numero d'onda contro la finestra WKB**,
non la stima di frequenza. Detto sotto la eq. (3.9) `dL/L = L/W`, cioe' il
criterio di risoluzione: uno stimatore di centroide del picco lo rilassa del
proprio guadagno, ma il Block 15K ha misurato **2.014** elementi radiali
effettivi nel lobo, quindi quel guadagno e' dell'ordine di `sqrt(2)`, non ordini
di grandezza.

## Criterio di selezione della scena, terza e si spera ultima versione

- CP6: swell **stretto**. CP15: swell **bimodale**. Entrambi sbagliati, il primo
  per la ragione giusta.
- Ordinare per `eps = sigma_f / f_bar` del sistema dominante dentro un cono di
  `±20°` attorno al vettore d'onda immagine atteso: `eps <= 0.05` tiene la
  dispersione di `omega` sotto il 10%.
- Ordinare per **gradiente di fondo**: `|grad h| <= 2e-3` per `dh/h` sotto ~25%,
  `<= 5e-4` per ~10%. Vandenberg, a 8.79e-3, non poteva riuscire.
- Richiedere che lo swell sia abbastanza normale alla costa perche' il cono
  contenga la maggior parte dell'energia di banda.

Il rescreening dei 12539 sidecar STAC va rifatto con questi due numeri, non con
`d_omega > 0.29 rad/s`.

## File

`code/analyze_block16_buoy_spectrum_audit.py`,
`code/analyze_block16_width_criterion.py`,
`Vandenberg/results/analysis_block16/` (PNG + due JSON + questo file).

Fonti esterne consultate: NDBC Technical Document 03-01 (`wavemeas.pdf`, 33 DOF
equivalenti per DACT WA, 48 per GSBP WDA), NDBC `wavespectra.shtml` (tabelle di
banda WPM e WA/DWA), CDIP `data_processing` (le Datawell calcolano lo spettro a
bordo, CDIP decodifica) e CDIP `MEM_2dspectra` (64×72, e la nota di CDIP che il
MEM «makes narrow directional spectra for swell in the Pacific»).
