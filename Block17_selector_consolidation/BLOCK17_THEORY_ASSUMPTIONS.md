# Block 17 — assunzioni teoriche e criteri esplorativi

## Banda sintetica

Il generatore corretto campiona direttamente le frequenze dalla distribuzione energetica gaussiana target, con potenza attesa uguale per componente e fase casuale. Il generatore legacy campionava già da quella gaussiana e applicava poi un secondo peso gaussiano: il prodotto restringe la deviazione standard energetica a circa `σ/√2`.

I test usano i 32 tempi BP12 archiviati e irregolari, non una griglia uniforme inventata. `epsilon` indica `σ_f/f0` della **densità energetica target**. Non è un errore su `f0`.

## Risoluzione e precisione

La spaziatura Fourier `1/T` e la scala spaziale `2π/W` descrivono la griglia/larghezza di risposta dovuta al supporto. Un tono isolato off-grid, con modello corretto e SNR sufficiente, può essere stimato con precisione più fine. Questa possibilità non prova che un campo oceanico largo o multimodale abbia la stessa precisione.

## Dispersione e propagazione degli errori

Per `F(k,ω,h)=ω²-gk tanh(kh)=0`:

- `dh/dk = -F_k/F_h`;
- `dh/dω = -F_ω/F_h`;
- `Var(h) = h_k² Var(k) + h_ω² Var(ω) + 2 h_k h_ω Cov(k,ω)`.

Il confronto su una banda finita usa `ω(k,h)` per ogni k. La derivata prevista è la velocità di gruppo `dω/dk`, e una variazione spaziale di profondità è pertinente solo lungo la direzione di propagazione.

Il calcolo numerico esemplificativo (`h=12 m`, `T=13 s`) dà `k=0.0467911 rad/m` e `c_g=9.38474 m/s`. Con incertezze puramente illustrative `σ_k=0.002 rad/m`, `σ_ω=0.02 rad/s`, `σ_h` varia da 0.748 a 2.235 m passando da correlazione +0.8 a −0.8: la covarianza non è trascurabile. Questi numeri sono **esplorativi**, non gate di selezione né inversione.

