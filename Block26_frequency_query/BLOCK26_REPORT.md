# Block 26 — query per la sola misura della frequenza assoluta

Data: 2026-09-16. Obiettivo cambiato: **si misura `ω` e basta.** Batimetria e
lunghezza d'onda non sono più criteri. Nessuna rete, nessun dato SAR, nessun
download raccomandato.

## Perché il cambio di obiettivo semplifica davvero

`ω` è **l'invariante cinematico**: in assenza di gradienti di corrente la
frequenza assoluta si conserva nel trasporto verso riva (eq. 2.33). Quindi
`ω` misurata alla boa vale anche nella scena **qualunque sia la profondità**, e
boa e scena non devono stare alla stessa quota né sullo stesso fondale.

Cade tutto l'impianto che ci ha bloccati per cinque blocchi:

| criterio | prima | ora |
|---|---|---|
| profondità, `∇h`, `kh` | gate | **irrilevante** |
| `δL/L ≤ 0.1` (10 λ nella ROI) | gate duro | **≥ 3 λ**, serve solo a isolare il lobo dal DC |
| tetto sul periodo dalla ROI | bloccante | **cade** |
| `Hm0 ≥ 1.5 m` | gate | sostituito dalla **ripidità** |

**L'unica eccezione è la corrente.** `ω = σ + k·U`: un estuario con maree di
1–1.5 m/s sposta `ω` di una quantità che non sappiamo separare. Per una misura
di frequenza **assoluta** è il confonditore diretto, quindi la coda è ordinata
per **rischio di corrente**, non per vicinanza della boa.

## Il gate di imaging corretto: ripidità, non altezza

La modulazione di tilt scala con la **pendenza** dell'onda:

| caso | Hm0 | T | L | H/L |
|---|---|---|---|---|
| Block21 cand. 1 (swell lungo) | 0.82 m | 15.4 s | 369 m | **0.0022** |
| Block18 Golfo del Messico | 1.01 m | 4.26 s | 28 m | **0.0357** |

**Sedici volte più ripido**, con un'altezza appena maggiore. Per l'imaging conta
la seconda colonna. Il gate `Hm0 ≥ 1.5 m` del Block25 era il proxy sbagliato e va
sostituito da `H/L ≥ 0.010`.

## La query

Gate offline, applicati su tutte le 10 140:

```
O1  prodotto complesso PUBBLICO (*_size_bytes non nullo, non il flag STAC)
O2  MARE APERTO: ocean_fraction >= 0.99 oppure nessuna costa nell'impronta
O3  una stazione con spettro direzionale entro 50 km
```

```
10 140 totali
   539 con complesso pubblico + stazione + ROI
    37 MARE APERTO                                  <- la coda
```

Solo **37 scene su 10 140** sono sostanzialmente mare aperto con una boa. La
distribuzione di `ocean_fraction` nel pool di 539 lo dice da sola: 37 sopra 0.99,
5 fra 0.90 e 0.99, 13 fra 0.80 e 0.90, **358 sotto 0.50**.

### I cluster, con la profondità GEBCO al centro ROI come proxy di apertura

| stazione | n | posizione | h | corpo d'acqua | rischio corrente |
|---|---:|---|---|---|---|
| **42094** | **18** | 29.000 N, 90.000 W | **−24 m** | piattaforma aperta, delta del Mississippi | **basso** |
| 41052 | 1 | 18.300 N, 64.826 W | +4 m (isola) | Isole Vergini, baia | medio |
| 44063 | 7 | 38.992 N, 76.375 W | −17 m | estuario Chesapeake | **alto (marea)** |
| 44064 | 3 | 36.974 N, 76.129 W | −11 m | Hampton Roads | **alto (marea)** |
| 44087 | 3 | 36.978 N, 76.163 W | −10 m | Hampton Roads | **alto (marea)** |
| 44060 | 5 | 41.254 N, 72.343 W | −7 m | Long Island Sound | **alto (marea)** |

**Il cluster 42094 è l'unico a basso rischio di corrente**, ed è anche il più
profondo, il più esteso (18 scene, dwell 5.4–17.0 s) e l'unico con `ROI = 1500 m`
e `ocean_fraction = 1.000` su tutte le epoche. Tutto il resto è estuario.

### E contiene già la scena meglio allineata dell'archivio

`2025-12-02-16-00-55_UMBRA-07` è la scena che il Block18 aveva analizzato:
**differenza assiale 2.33°**, `ocean_fraction 1.000`, ROI 1500 m, dwell 17.0 s,
SICD 17.01 GB + CPHD 74.48 GB, boa 42094 a 13.08 km.

Il Block18 l'aveva scartata perché a `kh = 4.4` non sente il fondo. **Sotto il
nuovo obiettivo quel motivo non esiste più.** Con `T = 4.26 s` e `ROI 1500 m` dà
**53 lunghezze d'onda nella finestra** e `H/L = 0.036`: è la configurazione
migliore del catalogo per misurare una fase.

## Consegna

- `BLOCK26_QUERY_QUEUE.csv` — 37 scene, ordinate per rischio di corrente, poi
  distanza dalla boa, poi dwell.
- `run_block26_frequency_query.py` — interroga la boa e applica i quattro gate
  che la richiedono:
  - **B1** differenza assiale `≤ 35°` — criterio **primario**, minimizza cut-off
    e velocity bunching;
  - **B2** ripidità `H/L ≥ 0.010`;
  - **B3** almeno **3** lunghezze d'onda nella ROI (isolare il lobo, non misurare
    `k`);
  - **B4** rotazione di fase fra 45° e 1080° sulla base `0.65 × dwell`.

  Soglie **descrittive, non calibrate**. Riusa `umbra_sar.reference_recovery`
  (Block17/18). Budget 150 transazioni / 100 MiB — sono 6 stazioni e 37 scene.

Va eseguito sulla macchina dell'utente: in questa sessione né il container né la
workspace locale raggiungono `dods.ndbc.noaa.gov`.

## Cosa aspettarsi

Delle 18 scene del Golfo conosciamo già un punto: la 2025-12-02 ha `Tp = 4.26 s`,
`Hm0 = 1.01 m`, allineamento 2.33°. Le altre 17 sono la stessa area in stagioni
diverse, quindi è ragionevole che almeno alcune passino tutti e quattro i gate.
La query serve a scegliere **quale**, e in particolare quella che combina il
migliore allineamento con la ripidità maggiore.

Nota sui costi: il cluster del Golfo ha SICD da 9.5 a 17.0 GB e CPHD fino a
74.5 GB. Se il gate seleziona una scena lì, **il primo download da fare è il
SICD**, non il CPHD: per una prima misura di fase l'immagine complessa basta, e
il Block12 ha mostrato che la retroproiezione da CPHD serve a correggere l'asse
dei tempi — che è un problema successivo, non il primo.
