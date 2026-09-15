# Nota aperta — inviluppo di accuratezza risoluzione / WKB

Stato: **esplorativa, non validata, non un gate.** Nessun risultato congelato
dipende da questa nota. Conservata nel repository perché il ragionamento è
riutilizzabile e perché i suoi errori sono stati individuati e vanno registrati.

## Il bilancio proposto

Da tre ingredienti già nella tesi — `δL/L = L/W` (eq. 3.9), `δh/h ≥ A·δL/L` con
`A = 1 + sinh(2kh)/(2kh)`, e la condizione che lo smear da shoaling del picco
attraverso la finestra non superi un elemento di risoluzione — segue una forma
chiusa. Differenziando `ω² = gk·tanh(kh)` a ω fissata:

    |dk/dh| = k² / (n·sinh(2kh)),     n = ½(1 + 2kh/sinh 2kh)

e quindi

    (δh/h)_min = A(kh) · sqrt( 2π·∇h / (n(kh)·sinh(2kh)) )

Scala come `sqrt(∇h)`, dipende dalla profondità solo attraverso `kh`, e ha un
minimo interno a `kh ≈ 1.20` (`h/L ≈ 0.19`), dove vale `4.14·sqrt(∇h)`.
Verificata contro una griglia numerica su `W` entro il 2.7%.

## Perché NON va usata come gate

Quattro obiezioni, tutte accettate:

1. **`δk = 2π/W` è la risoluzione di Fourier, non l'errore di uno stimatore.**
   Un centroide su un lobo isolato ad alto S/N fa meglio di un fattore `G`. Il
   Block15K ha misurato 2.014 elementi radiali effettivi, quindi `G ≈ √2` su
   quel lobo — ma non è una legge generale.
2. **Gli errori su `k` e `ω` non sono indipendenti.** Componenti diverse dello
   stesso sistema ondoso soddisfano tutte la stessa relazione di dispersione
   alla stessa profondità: la loro larghezza spettrale è campionamento
   ridondante, non errore. Sommare `A·δL/L` e `B·δσ/σ` in quadratura
   **doppio-conta**. Il termine residuo corretto è la curvatura di `ω(k)` sul
   bin (un bias alla Jensen) più la varianza da campioni finiti, non la
   larghezza fisica dello spettro.
3. **Il termine che resta valido è l'altro:** dentro la finestra la profondità
   cambia, quindi a ω fissata `k` varia. Quello è un errore genuino e traccia
   con `W` in direzione opposta alla risoluzione. Risoluzione `∝ 1/W`, blur da
   shoaling `∝ W`: esiste un ottimo di `W` e un pavimento associato. **Questa
   parte sopravvive** ed è il nucleo difendibile.
4. **Il generatore sintetico usato per tarare il termine in frequenza era
   difettoso.** `band_trial()` estraeva le frequenze da una gaussiana di
   deviazione `ε·f0` e poi ne ripesava la potenza con la stessa gaussiana,
   producendo `σ_eff ≈ ε·f0/√2`. Confermato numericamente dal Block17
   (rapporto misurato 0.7062–0.7079 contro 1/√2 = 0.7071). Le soglie
   `ε ≤ 0.05` e i percentili derivati da quel generatore **non sono
   utilizzabili nella forma proposta**.

## Cosa resta

- La struttura del compromesso risoluzione / finestra WKB.
- L'osservazione che `A` cresce esponenzialmente in acqua profonda, quindi
  esiste una banda `kh` utile e il metodo è intrinsecamente una tecnica di
  acqua intermedia.
- La dipendenza `sqrt(∇h)` del termine spaziale.

Tutto il resto va riderivato con la covarianza `k`–`ω` esplicita e con un
modello di stimatore dichiarato, prima di poter diventare un criterio.
Riferimenti: `Block17_selector_consolidation/BLOCK17_THEORY_ASSUMPTIONS.md`,
`BLOCK17_ERRATA.md`.
