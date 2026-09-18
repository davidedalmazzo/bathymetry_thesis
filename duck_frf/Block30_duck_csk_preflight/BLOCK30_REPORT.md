# Block 30 — Duck (FRF, NC): le 18 scene COSMO-SkyMed d'archivio

Data: 2026-09-16. Nessuna rete verso prodotti SAR, nessun download, nessuna
inversione, nessuna correzione di `q`. Le soglie citate sono **descrittive**,
non calibrate.

## Contesto

Blocchi 24→28 hanno stabilito che il catalogo Umbra non contiene la
combinazione «impronta adeguata + boa rappresentativa». Block 28 si è fermato
perché con una sola boa a 8.75 km la conservazione di `ω` fra boa e ROI restava
un'**ipotesi non falsificabile**.

Duck cambia proprio questo: il FRF ha un transetto cross-shore di nove
strumenti direzionali da 4.5 m a 26 m di profondità, pubblici via OPeNDAP su
`chldata.erdc.dren.mil`. Con quelli la conservazione di `ω` si **misura**.
Valutazione completa del sito nelle note di progetto
(`block30-duck-frf-valutazione-sito`).

## Cosa contiene l'export CLEOS

18 feature, finestra 2019-09-11 / 2026-09-16, area Duck. Sono **tutte identiche
per classe**:

| campo | valore (tutte e 18) |
|---|---|
| mission | COSMO-SkyMed (**I Generation**) |
| acquisition_mode | **Spotlight-2** (Enhanced Spotlight) |
| resolution_class | VHR1b (classe 1 m) |
| polarization | **HH** |
| ownership / status | public / ARCHIVED |
| lookside | RIGHT |
| piattaforme | CSK1 (7), CSK2 (6), CSK4 (5) |
| periodo | 2019-10-02 … 2021-10-13 |
| impronta | ~10.5 × 10.3 km |

**Nessuna scena di seconda generazione, nessuno Spotlight-2A.**

## Correzione: 7.9 s non è il dwell

I metadati riportano `start_datetime`/`end_datetime` distanti 7.36–7.97 s.
È la durata del **data take**: il tempo necessario al fascio per scorrere sui
10 km di scena in azimut. **Non è il tempo di illuminazione del singolo
bersaglio**, che è l'unica quantità che limita la separazione fra sub-look.
Confondere le due cose sovrastima il dwell di circa un fattore 5.

Il dwell per punto si ricava dalla risoluzione azimutale:
`T_dwell = λ·R / (2·δ_az·V)`, con λ = 0.03125 m, δ_az = 1.0 m, V = 7.6 km/s
e R calcolato dall'incidenza e dalla quota CSK (619 km).

| incidenza | R slant | T_dwell | T_base (0.65) | Δφ @6 s | @8 s | @10 s | @12 s |
|---|---|---|---|---|---|---|---|
| 23.7° | 670 km | 1.38 s | 0.90 s | 54° | 40° | 32° | 27° |
| 30.5° | 708 km | 1.45 s | 0.95 s | 57° | 43° | 34° | 28° |
| 34.6° | 737 km | 1.51 s | 0.98 s | 59° | 44° | 35° | 30° |
| 40.0° | 784 km | 1.61 s | 1.05 s | 63° | 47° | 38° | 31° |
| 47.7° | 875 km | 1.80 s | 1.17 s | 70° | 53° | 42° | 35° |
| 50.6° | 918 km | 1.89 s | 1.23 s | 74° | 55° | 44° | 37° |

Se la risoluzione dichiarata è la larghezza a −3 dB con finestra di pesatura
(~1.25×), il dwell reale è ~25% maggiore e i Δφ della tabella sono un
**limite inferiore**. Da verificare sul prodotto, non da assumere.

Con la regola di progetto di Romeiser (Δφ ≳ 45°) queste scene passano **solo
per mare corto**: T = 6–8 s dentro o al bordo, T = 10–12 s sotto. È l'inverso
dell'intuizione — qui il mare di vento aiuta, lo swell lungo no.

### La soglia dei 45° non è un criterio di rivelabilità

I 45° sono una regola di progetto, non una soglia di rivelazione. Il criterio
vero è `Δφ / σ_Δφ`, con `σ_Δφ` dipendente dal numero di celle spettrali
indipendenti e dalla coerenza fra sub-look. Su 10 × 10 km con L ≈ 116 m le
celle indipendenti sono molte, e c'è un ottimo: a Δt piccolo la coerenza è alta
ma il segnale di fase è piccolo, a Δt grande accade il contrario.

**Test a costo zero, nessun dato nuovo**: girare la catena sintetica esistente
(Block 6 / 12 / 20) a Δt = 0.9–1.2 s, L = 116 m, con l'Hs reale, e misurare
`σ_Δφ`. Se `Δφ/σ_Δφ` risulta comodamente > 5 le scene sono utilizzabili e la
regola dei 45° era troppo conservativa; se no si scartano con un argomento
quantitativo invece che con una regola del pollice.

## Geometria: è la sorpresa positiva

| nodo | N | φ (angolo k–range, **assunto**) | estensione al largo | waverider-17m nell'impronta |
|---|---|---|---|---|
| ASCENDING | 10 | 8.5–11.2° | 2.5–6.0 km | 8 / 10 |
| DESCENDING | 8 | 29.3–31.2° | **7.6–9.8 km** | 8 / 8 |

- **16 scene su 18 contengono la waverider da 17.8 m (NDBC 44056) dentro
  l'impronta.** Non vicina: dentro. Il problema di rappresentatività che aveva
  bloccato Block 28 sparisce.
- La waverider da 25 m (44100) è fuori da tutte: sta a 16 km, l'impronta è 10 km.
- Tutte contengono il molo FRF, quindi anche gli AWAC del transetto.

φ è calcolato con direzione d'onda **assunta** a 250°T (asse cross-shore FRF
70°T, stimato dai bearing molo→44056 = 57.7° e molo→44100 = 59.2°). Il gate
vero usa la direzione **misurata**, che arriva da `run_block30_frf_conditions.py`.

### Compromesso per fascio

| fascio | nodo | inc | T_dwell | φ | al largo | nota |
|---|---|---|---|---|---|---|
| ES-0C | ASC | 23.7° | 1.38 s | 8.5° | 2.5–3.2 km | NRCS migliore, dwell peggiore, **44056 fuori impronta** |
| ES-08 | ASC | 34.6° | 1.51 s | 9.5° | 5.3–6.1 km | compromesso migliore |
| ES-23 | ASC | 50.6° | **1.89 s** | 11.2° | ~5.5 km | dwell migliore, ma HH a 50° = NRCS peggiore |
| ES-05/13/20 | DES | 30–48° | 1.45–1.80 s | 29–31° | **7.6–9.8 km** | più mare, angolo peggiore |

### Rischio di polarizzazione

**Tutte e 18 sono HH.** Per lo scattering di Bragg sul mare HH è nettamente più
debole di VV a incidenza medio-alta. Combinato con i 47–51° di ES-20 e ES-23
questo è un rischio concreto di SNR, e l'SNR entra direttamente in `σ_Δφ`, cioè
nella quantità critica della sezione precedente.

## Una data privilegiata

**2021-10-13 22:45 UTC** (CSK1, ES-20, DESCENDING, inc 47.7°, 9.6 km al largo,
44056 dentro l'impronta) cade dentro la campagna **DUNEX** (set 2021 – ago
2022), durante la quale Hereon aveva installato al FRF un radar marino
coerente. Se era operativo quella notte si avrebbe la tripla coincidenza:
SAR satellitare, radar coerente da costa, array in-situ completo.

## Cosa manca

Lo **stato di mare nei 18 istanti**: Hs, Tp, direzione media, spread. Con
quelli si chiude il gate:

1. `Δφ/σ_Δφ` (non la regola dei 45°)
2. angolo φ fra `k` **misurato** e direzione di range
3. `L / sin(φ) ≥ λ_c` con `λ_c = 2π·β·σ_ur`, β = R/V per scena
4. estensione al largo sufficiente per ≥ 10 lunghezze d'onda

Il server FRF risponde ma va interrogato **in locale**: il proxy dell'ambiente
cloud blocca l'accesso OPeNDAP a `chldata.erdc.dren.mil`.

## File

| file | contenuto |
|---|---|
| `cleos_export/results_COSMO-SkyMed_20190911_20260916.json` | export CLEOS grezzo (GeoJSON) |
| `cleos_export/results_COSMO-SkyMed_20190911_20260916.kml` | stesso export, KML |
| `BLOCK30_CSK_DUCK_SCENES.csv` | tabella geometrica, 18 righe |
| `../code/run_block30_scene_geometry.py` | rigenera il CSV dall'export |
| `../code/run_block30_frf_conditions.py` | interroga il FRF, produce il gate |

Riproduzione:

```powershell
.\.venv-umbra-thesis\Scripts\python.exe code\run_block30_scene_geometry.py `
    Block30_duck_csk_preflight\cleos_export\results_COSMO-SkyMed_20190911_20260916.json `
    Block30_duck_csk_preflight

.\.venv-umbra-thesis\Scripts\python.exe code\run_block30_frf_conditions.py --smoke
.\.venv-umbra-thesis\Scripts\python.exe code\run_block30_frf_conditions.py --months 202110 --gauges waverider-17m
.\.venv-umbra-thesis\Scripts\python.exe code\run_block30_frf_conditions.py
```

## Stato epistemico

**Osservato**: classe, modo, polarizzazione, incidenze, poligoni, data take,
disponibilità degli strumenti FRF.
**Calcolato**: slant range, β, T_dwell, T_base, Δφ, heading, direzione di
range, estensioni cross-shore, appartenenza delle boe all'impronta.
**Assunto, da confermare**: asse cross-shore FRF a 70°T; direzione d'onda a
250°T; fattore di allargamento della finestra di pesatura; convenzione di
`waveMeanDirection` (assunta «da cui viene»).
**Non valutato**: stato di mare nei 18 istanti; se il prodotto SCS preservi
l'intera banda Doppler e i parametri di steering necessari a datare i
sub-look; variazione del dwell attraverso la scena in azimut; operatività del
radar Hereon la notte del 2021-10-13; pulizia effettiva del campo d'onda
(niente analisi AIS).
