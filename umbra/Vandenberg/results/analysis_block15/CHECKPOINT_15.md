# Checkpoint 15 — Una miscela e una componente singola sono indistinguibili su questo dwell

Data: 2026-09-14. Nessuna nuova formazione, nessun download. Tutto ricavato dai
sotto-look retroproiettati gia' su disco (Block 12, supporto 1440 m; Block 13,
supporto 3000 m) e dai tempi di look misurati.

## Perche' questo blocco esisteva come lacuna

Il CHECKPOINT_9 ha validato lo stimatore end-to-end e autorizzato il ritorno al
dato reale. Ogni suo caso, incluse le sette varianti di realismo (rumore bianco,
speckle fisso, speckle decorrelante, ampiezze disuguali, picchi a larghezza
finita, detrend+Tukey, 80% di sovrapposizione), porta **una sola** frequenza
angolare. Il TEST B «constant-frequency 1.818e-06» e' un controllo a frequenza
unica. **Due componenti con omega diverse nello stesso bin non sono mai state
simulate.**

Quella configurazione non e' ipotetica a Vandenberg: e' imposta dalla geometria.
La boa 46218 porta l'8.9% di m0 a 13.33 s e l'8.2% a 15.38 s. A h = 16.44 m sono
158.70 m e 186.15 m, separazione 0.00584 rad/m contro un passo spettrale di
0.00628 rad/m su 1000 m: **non risolvibili in numero d'onda**. In frequenza
distano 0.0629 rad/s, battimento 100.0 s, contro un'osservazione di 21.836 s:
**0.218 cicli di battimento, non risolvibili in tempo.**

## Block 15a — cosa restituisce lo stimatore su una miscela (sintetico)

Stimatore identico a quello della pipeline, tempi di look **reali**.

Miscela deterministica delle due componenti della boa, al variare del rapporto
di ampiezza e della fase relativa:

| A2/A1 | fase 0 | fase pi |
|---|---|---|
| 0.25 | 0.4607 | 0.4828 |
| 0.50 | 0.4520 | 0.4916 |
| 0.96 | 0.4407 | 0.4596 |
| 1.00 | 0.4399 | 0.4399 |
| 2.00 | 0.4279 | 0.3883 |

- intervallo restituito: **0.3875 – 0.4916 rad/s**
- **R² minimo su tutte le miscele: 0.9973**

Quindi: **un R² alto non distingue una componente singola da una miscela.** I
Block 4, 6, 12 e 13 hanno usato ripetutamente l'alta linearita' della rampa come
prova di componente pulita (CP4 R² = 0.998288, CP12 0.9945, Block 13 fino a
0.998). Quell'inferenza non e' valida.

Intera banda di swell della boa in un solo bin, 200 realizzazioni con fasi
relative casuali: mediana **0.4653**, p10–p90 0.3825–0.5513, estremi
0.2715–0.6532, R² mediana 0.9997.

Controllo asimmetrico, ed e' il risultato che sopravvive: **una componente
singola a 13.33 s piu' speckle decorrelante a S/N 0.3 resta centrata su 0.4719
rad/s, p10–p90 0.4645–0.4796.** Il rumore allarga, non sposta. Il valore
osservato 0.4121 **non e' raggiungibile** da un 13.33 s misurato male.

## Block 15b — il dato reale non discrimina

Tre osservabili, su entrambi i supporti. Correzione preliminare necessaria:
ogni look porta l'inviluppo di illuminazione del dwell (escursione misurata
3.26× su Block 12, 2.91× su Block 13). Senza rimuoverlo, sia il test di
stazionarieta' sia l'ampiezza per look sono confusi. Normalizzato con la mediana
di una banda di controllo dominata da speckle (15–60 m).

**1. Stazionarieta' di |C|.** Per una componente singola stazionaria il modulo
del cross-spettro dipende solo dal lag; per una miscela dipende anche dal tempo
assoluto. Coefficiente sul tempo medio al bin di picco: −0.0842 (Block 12),
−0.0826 (Block 13).

Il sigma parametrico dava 39.8 e 47.9. **E' inflazionato**: le 496 coppie
provengono da 32 look e non sono indipendenti. Sugli stessi bin di sola speckle
lo stesso statistico vale gia' 15.9–17.3 sigma in mediana. Calibrando sul nullo
empirico, il coefficiente del bin di picco sta a **0.5 volte** (Block 12) e
**0.6 volte** (Block 13) la scala del nullo — **21° e 40° percentile**. Nessuna
non stazionarieta' rilevabile.

**2. Ampiezza per look.** Dopo normalizzazione, declino monotono di 3.48×
(Block 12) e 2.99× (Block 13). Degenere con la decorrelazione: su 0.218 cicli di
battimento un coseno declina in modo monotono esattamente come un decadimento.

**3. Confronto fra modelli** su 24 e 60 bin (potenza > 10% del picco, R² > 0.95).
Componente singola con omega libera (3 parametri), la stessa con inviluppo di
decorrelazione (4), la coppia della boa con **omega fissate** a 0.4714 e 0.4085
e sole ampiezze e fasi libere (4).

| | Block 12 | Block 13 |
|---|---|---|
| dAIC coppia − singola, mediana | +1.6 | +1.9 |
| la coppia vince in | 0/24 | 1/60 |
| dAIC coppia − singola con decorrelazione | +3.0 | +99.6 |
| la coppia vince in | 10/24 | 17/60 |
| A2/A1 recuperato, mediana | 0.99 | 0.97 |

**La coppia non batte mai una componente singola a omega libera.**

## Verdetto

Il dato reale **non puo'** separare una componente singola da una miscela su
questo span, e il Block 15a spiega perche': su 0.218 cicli di battimento le due
ipotesi sono osservazionalmente equivalenti. Il fallimento del test 15b non e'
evidenza contro la miscela — e' la conferma del limite di identificabilita'.

Cio' che resta stabilito:

1. **R² non ha potere diagnostico** in questa configurazione. Va rimosso dalla
   catena come criterio di qualita' della componente.
2. **Il valore osservato non e' un 13.33 s misurato con rumore.** Il rumore
   allarga di ±0.008 rad/s, non sposta di 0.06.
3. **La miscela resta la spiegazione piu' economica**, ma non e' dimostrabile
   qui, e nemmeno confutabile.
4. Le esclusioni dei Block 11–14 restano valide come esclusioni, ma tutte
   presupponevano che omega fosse la frequenza di **una** componente. Quella
   premessa non e' verificabile su questa scena.

Nota trasversale: il picco esce a **130.43 m** sul supporto da 3000 m,
**130.91 m** su quello da 1440 m e **130.79 m** sulla catena SICD da 540 m. Tre
supporti e due catene di formazione indipendenti. Il lato spaziale e' solido.

## Igiene: JSON del Block 14

Tre sezioni non prodotte da alcuno script — `azimuth_cutoff.interpretation`,
`anisotropy.controlled_for_wavelength` e l'intero `model_comparison`, dove vive
`q = 0.789` — sono state spostate, verbatim, in
`manual_annotations_unverified`. Una di esse contraddice la chiave
`anisotropy.verdict` scritta dallo script. La contraddizione resta irrisolta ed
e' ora dichiarata nel file. `q = 0.789` non va usato finche' non e' rigenerato
da codice.

## Conseguenze operative

- Il criterio di selezione della scena cambia segno. Il CP6 chiedeva **swell
  stretto**; questa analisi mostra che uno swell stretto e' la condizione in cui
  la misura non e' identificabile. Serve **swell bimodale**, con
  `d_omega * T_dwell > 2*pi`: con 22 s di dwell, sistemi che differiscono di
  almeno 0.29 rad/s.
- Su Vandenberg resta separabile la coppia 10.27 / 14.48 s trovata dal Block 13:
  `d_omega` = 0.178 rad/s, `dk` = 0.0163 rad/m a h = 25 m, Rayleigh a W = 385 m e
  smear da shoaling pari a 0.27 volte la separazione a W = 1000 m. E' l'unica
  configurazione a due componenti su cui si possa tentare la eq. (2.47).
- Lo sweep sulla durata dei look resta non giustificato: non cambia la miscela
  spettrale e il CP10 ha gia' predetto un nullo (`Triggered: False`,
  dw/dk 8.5725 → 8.5782 m/s da 6.0 s a 1.5 s).

## File

`code/validate_block15_estimator_mixture.py`, `code/analyze_block15_mixture.py`,
`code/fix_block14_json_provenance.py`,
`Vandenberg/results/analysis_block15/BLOCK15A_ESTIMATOR_MIXTURE.json`,
`BLOCK15B_MIXTURE_block12.json`, `BLOCK15B_MIXTURE_block13.json`.
