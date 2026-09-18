# Checkpoint 11 - L'asse dei tempi dei sub-look non spiega il deficit di omega

Data: 2026-09-01. Nessuna immagine SICD riletta, blocco segnale CPHD mai aperto.
Solo blocco PVP del CPHD, sub-look complessi gia' memorizzati di Block 4 e stack
di fase non avvolta di Block 6.

## Ipotesi in prova

Block 3/4 etichetta ogni sub-look con il **centro geometrico** della sua banda
Doppler, mappato in slow time invertendo `k_col(t)` sul PVP. Quell'etichetta e'
esatta solo se la densita' spettrale azimutale e' piatta sul supporto
processato. Non lo e' per ipotesi: il SICD dichiara `Grid.Col.WgtType = SVA`
senza campioni `WgtFunct`, il pattern d'antenna a due vie affusola
l'illuminazione, e Block 4 moltiplica una Tukey(0.25) dentro ogni banda.

Sotto una pesatura piccata al centro dell'apertura il centroide di potenza di
ogni banda e' tirato verso l'interno, il braccio di leva della regressione
fase-tempo si accorcia e

    omega_stimata = omega_vera * shrink,   shrink <= 1,

in modo **moltiplicativo e indipendente dal numero d'onda**, perche' e' un
riscalamento dell'asse dei tempi. Il segno e' una previsione, non un fit: una
pesatura centrata puo' solo accorciare, quindi omega puo' solo uscire bassa.
E' esattamente il verso dell'errore osservato. Block 9 non poteva rilevarlo:
il suo surrogato costruisce l'apertura da una portante casuale a modulo
unitario, quindi ha spettro azimutale piatto per costruzione e shrink
identicamente uno.

Shrink richiesto per chiudere il divario, usando il periodo dominante NDBC
46218 di 13.333 s (omega = 0.47124 rad/s, invariante rispetto allo shoaling e
quindi indipendente dalla profondita' assunta): **0.7448**.

## Test A - centroide energetico misurato

Per ogni sub-look memorizzato si calcola lo spettro azimutale del ritaglio,
`|S_i(k)|^2` mediato sulle 1200 righe di range, e da esso il centroide di
potenza della banda, riportato in slow time con la stessa inversione PVP.

La mappatura `k_col(t)` e' stata ricostruita indipendentemente e riproduce
`Grid.Row.KCtr` a `64.91011596200` contro `64.91011596201477` del SICD.

| ROI | shrink | span geometrico | span energetico | residuo rms |
|---|---|---|---|---|
| nearshore | **0.9835** | 11.5894 s | 11.3888 s | 55.3 ms |
| land_control | 1.0040 | 11.5894 s | 11.7936 s | 290.2 ms |

Lo spostamento del singolo look va da `+0.194 s` (look 1) a `-0.007 s`
(look 11); la potenza fuori banda e' 0.01%, quindi il ritaglio azimutale non
contamina la misura.

**L'ipotesi e' falsificata.** Servivano 0.745, si misura 0.983. La pesatura
ricostruita non e' un taper simmetrico ma una rampa monotona da 0.42 a 1.0
attraverso l'apertura: una rampa sposta tutti i centroidi nello stesso verso e
lascia lo span quasi invariato, che e' precisamente perche' lo shrink e' vicino
a uno. Il controllo su terra, con un profilo spettrale completamente diverso,
da' 1.0040: l'effetto e' strumentale e piccolo, non dipendente dalla scena.

Diagnostica secondaria: la potenza azimutale ha una tacca stretta a
`t = 7.111 s` che scende a 0.149 contro 0.40 e 0.52 nei bin vicini. E' interna
all'apertura e non sposta i centroidi, ma va segnalata come possibile notch RFI
o gruppo di impulsi degradati.

## Test B - rifit di Block 6 sui tempi misurati

Rifittando lo stack di fase con i tempi energetici (la pendenza originale e'
riprodotta a `3.3e-16 rad/s` sui tempi geometrici, quindi il rifit e' l'unica
differenza):

| grandezza | tempi geometrici | tempi energetici |
|---|---|---|
| omega al picco congelato (60,63) | 0.35097 rad/s | 0.35695 rad/s |
| T | 17.902 s | 17.602 s |
| h da dispersione, lambda = 130.79 m | 5.57 m | 5.77 m |
| R^2 | 0.9983 | 0.9990 |

Il rapporto omega_nuova/omega_vecchia sui 48 bin ad alta qualita' sta fra
1.01533 e 1.01718, uno spread dello 0.18%: la correzione **e'** esattamente un
riscalamento dell'asse dei tempi, come previsto dal meccanismo. E' solo troppo
piccola di un fattore 15 rispetto a quanto serve.

La correzione va comunque adottata: 0.35695 rad/s e' l'etichetta fisicamente
corretta, e la profondita' implicata sale da 5.57 a 5.77 m contro una mediana
misurata di 11.00 m nella ROI storica.

## Test C - il deficit dipende dal baseline che lo misura?

Gli undici look di Block 4 sono sovrapposti all'80% in Doppler. Per due look
sovrapposti il cross-spettro e'

    <A_i A_j*> = int int w_i(t) w_j(t') rho(t-t') exp(-i omega (t-t')) dt dt'

con `rho` la coerenza di scena in slow time. Se `rho` e' larga il doppio
integrale si fattorizza e la fase e' esattamente `-omega (t_i - t_j)`, la regola
del centroide. Se `rho` e' stretta l'integrando si concentra su `t = t'`, dove
il fattore di fase vale uno, e la fase misurata e' tirata verso zero: omega esce
bassa, tanto piu' quanto maggiore e' la sovrapposizione. La coerenza misurata
scende da 0.97 fra look adiacenti a 0.56 fra le ancore disgiunte, quindi il
regime non e' ipotetico.

Ricostruite tutte le 55 coppie dallo stack di fase:

| passo | coppie | dt medio | overlap | omega picco | omega lobo |
|---|---|---|---|---|---|
| 1 | 10 | 1.139 s | 0.800 | 0.3687 | 0.3776 |
| 2 | 9 | 2.282 s | 0.600 | 0.3664 | 0.3862 |
| 3 | 8 | 3.427 s | 0.400 | 0.3665 | 0.3799 |
| 4 | 7 | 4.558 s | 0.200 | 0.3596 | 0.3780 |
| 5 | 6 | 5.674 s | 0.000 | 0.3511 | 0.3776 |
| 6 | 5 | 6.809 s | 0.000 | 0.3521 | 0.3794 |
| 7 | 4 | 7.976 s | 0.000 | 0.3561 | 0.3797 |
| 8 | 3 | 9.140 s | 0.000 | 0.3614 | 0.3792 |
| 9 | 2 | 10.268 s | 0.000 | 0.3617 | 0.3774 |
| 10 | 1 | 11.389 s | 0.000 | 0.3619 | 0.3757 |

Regressione pesata: `d omega / d(overlap) = +0.0071 +/- 0.0097 rad/s`,
`d omega / d(dt) = +0.00070 +/- 0.00061 rad/s per s`. Entrambe compatibili con
zero. Sulle 21 coppie a sovrapposizione nulla la mediana e' 0.3558 rad/s
`[0.3422, 0.3640]`; su tutte le 55 e' 0.3589 rad/s. La dispersione si restringe
al crescere di `dt`, come atteso per un rumore di fase che scala come `1/dt`.

**Il deficit non e' un artefatto di sovrapposizione ne' di decorrelazione.** La
fase misurata e' una rampa lineare genuina con una pendenza stabile su ogni
baseline da 1.14 s a 11.39 s, e su tutte le sovrapposizioni da 0.8 a 0.

## Diagnostica di supporto - il lobo riporta un numero solo

Fit pesato di `omega_osservata` contro `omega_dispersione(lambda, h)` sui 22 bin
del lobo primario:

| h | fit | rms | corr |
|---|---|---|---|
| 11.003 m | `0.2690 + 0.1935 * omega_disp` | 0.0105 | +0.892 |
| 13.100 m | `0.2648 + 0.1887 * omega_disp` | 0.0106 | +0.890 |
| 16.441 m | `0.2574 + 0.1873 * omega_disp` | 0.0109 | +0.886 |

La risposta alla dispersione e' il 19% di quella dovuta, con un grande offset
costante; `omega_osservata` varia solo del 6.1% di coefficiente di variazione
mentre `omega_disp` varia di un fattore 2.2 sullo stesso intervallo di
lunghezze d'onda. E' la firma quantitativa della lettura gia' proposta: su una
finestra da 540 m un treno d'onda non risolto deposita la **stessa** frequenza
in ogni bin della propria coda spettrale. Il lobo primario non porta
informazione indipendente su `omega(k)`, e nessun test di dipendenza da `k`
condotto su di esso puo' discriminare alcunche'.

## Stato del problema

Cause ora escluse per il deficit `omega_SAR = 0.3510` contro
`omega_boa = 0.4712` (rapporto 0.745):

- rampa di fase MTF statica (assorbita dall'intercetta del fit, che c'e');
- contaminazione periodica (limitata a 0.017 contro 0.127 rad/s necessari);
- misassegnazione del tempo Doppler (3.2 ms);
- drift bulk (richiederebbe 2.5 m/s);
- dipendenza azimutale o da velocity bunching (nessuna nella mappa di Block 6);
- errore software (Block 9);
- fisica minimale del forward model (Block 10);
- **scala dell'asse dei tempi (questo blocco: 1.7%, ne servivano 25%)**;
- **contaminazione da sovrapposizione o decorrelazione (questo blocco)**.

Resta un tasso di fase reale, stabile, di `-0.3510 rad/s` su un asse dei tempi
ora verificato, incompatibile con la cinematica di un'onda di gravita' di
`lambda = 130.79 m` su fondale di 11 m.

## Cosa fare, in ordine

1. Riformare i look sul supporto tutto-acqua da 1440 x 650 m e rifare la mappa
   di fase. Finche' il lobo riporta un numero solo, nessun test su `k` puo'
   discriminare. E' il passo raccomandato da Block 7 e mai eseguito.
2. Sweep sulla larghezza dei sub-look (`T_i` da 5.8 s a 1.5 s). Con lo shrink
   ora misurato la previsione della vecchia ipotesi di pesatura collassa a
   "omega costante"; lo sweep resta comunque il test dello smear di moto entro
   il singolo look (`beta * omega * sigma_ur * T_i = 8.15 m/s * T_i`, cioe' 36%
   di lambda su un look da 5.8 s).
3. Surrogato con velocity bunching in ground e slow time, non a modulo unitario:
   Block 9 e' cieco a qualunque effetto della forma dello spettro azimutale.

## File

- `BLOCK11_ENERGY_CENTROID.json`, `.png`, `BLOCK11_SUBLOOK_TIMES.csv`
- `BLOCK11_PAIRWISE_OMEGA.json`, `.png`
- `code/umbra_sar/aperture_weighting.py` (solo numpy; legge SICD_METADATA.json)
- `code/analyze_block11_energy_centroid.py`
- `code/analyze_block11_pairwise_omega.py`
