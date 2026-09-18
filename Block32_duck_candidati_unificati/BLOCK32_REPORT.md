# Block 32 — COSMO e TerraSAR-X su Duck, nella stessa classifica

Data: 2026-09-17. Unisce Block 30 (18 scene COSMO-SkyMed) e Block 31 (11 Staring
Spotlight TerraSAR-X). Nessun download SAR, nessuna inversione, nessuna correzione di q.

## Cosa avevamo trovato per COSMO

Export CLEOS, area di Duck: **18 acquisizioni, tutte identiche per classe** —
COSMO-SkyMed **prima generazione**, modo **Spotlight-2** (Enhanced Spotlight),
classe VHR1b, **HH**, pubbliche, archiviate, ottobre 2019 – ottobre 2021,
impronta ~10.5 × 10.3 km. Nessuna di seconda generazione, nessuno Spotlight-2A.

Dwell per bersaglio 1.38–1.89 s (**non** i 7.4–8.0 s del data take nei metadati),
Δφ a T = 10 s fra 32 e 44°. Sedici scene su diciotto contengono la Waverider a
17.8 m dentro l'impronta.

## La classifica unificata

Gate: margine cut-off ≥ 2, Δφ dentro [45°, 180°], ripidità H/L ≥ 0.008,
riferimento in-situ non scaduto. Figura di merito `Δφ·√A_mare`, proporzionale a
`Δφ/σ_Δφ` a parità di coerenza — più mare significa più finestre indipendenti,
e σ scende come √N.

| sensore | acq_utc | Hs | Tp | φ | Δφ | margine | H/L | mare km² | Δφ√A | boa |
|---|---|---|---|---|---|---|---|---|---|---|
| TSX-ST | 2020-11-10 11:15:43 | 0.83 | 7.39 | 7.8° | 154° | 7.5 | 0.0109 | 11 | **514** | no |
| TSX-ST | 2020-09-07 22:51:35 | 1.27 | 7.84 | 0.3° | 141° | 137 | 0.0151 | 12 | **486** | sì |
| TSX-ST | 2023-11-06 22:51:53 | 0.92 | 8.03 | 0.4° | 138° | 183 | 0.0106 | 12 | **482** | sì |
| **CSK** | **2020-09-09 10:42:54** | 1.16 | 5.50 | 0.7° | 64° | 24.5 | **0.0250** | 56 | **478** | sì |
| **CSK** | **2020-09-08 10:54:54** | 1.02 | 7.27 | 1.8° | 61° | 22.9 | 0.0137 | 57 | **459** | sì |
| TSX-ST | 2021-10-13 23:00:15 | 1.11 | 9.55 | 21.0° | 138° | 4.0 | 0.0101 | 9 | 409 | no |
| CSK | 2021-04-21 10:42:51 | 0.52 | 6.57 | 21.8° | 54° | 2.7 | 0.0082 | 55 | 399 | sì |

**I primi cinque stanno dentro il 7% l'uno dall'altro.** COSMO non è il parente
povero: perde un fattore 2.2 in rotazione di fase e lo recupera quasi tutto con
un'area di mare cinque volte più grande. E la CSK del 2020-09-09 ha la
**ripidità migliore dell'intero archivio** (H/L = 0.025, mare di vento a 5.5 s):
la modulazione di tilt scala con la pendenza dell'onda, non con Hs.

Su 29 scene ne passano 7: 4 TerraSAR-X su 11, 3 COSMO su 18.

## La finestra del 7–11 settembre 2020

**Sei acquisizioni in cinque giorni, due costellazioni, tre modi.**

| acq_utc | sensore | nodo | inc | Hs | Tp | φ | Δφ | margine | boa |
|---|---|---|---|---|---|---|---|---|---|
| 2020-09-07 22:51:35 | TDX-1 Staring | ASC | 23.2° | 1.27 | 7.84 | **0.3°** | 141° | 137 | sì |
| 2020-09-08 10:54:54 | CSK Spotlight-2 | ASC | 50.6° | 1.02 | 7.27 | **1.8°** | 61° | 22.9 | sì |
| 2020-09-08 22:44:52 | CSK Spotlight-2 | DES | 47.8° | 1.06 | 4.96 | 23.8° | 85° | 0.58 | sì |
| 2020-09-09 10:42:54 | CSK Spotlight-2 | ASC | 34.6° | 1.16 | 5.50 | **0.7°** | 64° | 24.5 | sì |
| 2020-09-11 11:07:08 | TSX-1 Staring | DES | 42.6° | 0.94 | 7.19 | 7.2° | 188° | 7.0 | no |
| 2020-09-11 22:50:52 | CSK Spotlight-2 | DES | 40.1° | 0.92 | 9.98 | 30.8° | 38° | 3.15 | sì |

Quattro delle sei passano o sfiorano i gate. Il dwell copre 1.4 → 5.8 s, un
fattore 4; le incidenze 23 → 51°; entrambi i nodi. L'array FRF registrava per
tutti e cinque i giorni.

È il nucleo di una proposta molto più forte di una scena singola: **la stessa
costa, la stessa settimana, due sensori indipendenti, e una scala di dwell
sufficiente a misurare dove crolla il rapporto Δφ/σ_Δφ** invece di postularlo
dalla regola dei 45° di Romeiser.

La Δφ della Staring dell'11 settembre avvolge (188°): non squalifica, basta
ridurre la base temporale da 0.65 a ~0.45 del dwell. È una libertà che le CSK,
con 1.4–1.9 s, non hanno.

## Due cose non verificate, e una è seria

**1. La risoluzione azimutale delle CSK è un'etichetta di classe, non una misura.**
Il valore 1.0 m con cui sono calcolati tutti i Δφ COSMO viene da
`resolution_class: VHR1b` nell'export CLEOS. Su TerraSAR-X abbiamo appena
imparato che `sensorResolution` nei metadati di prodotto **non** è la
risoluzione azimutale ma quella in range obliquo — cioè esattamente questo
genere di campo va verificato e non assunto. **Servono i metadati di prodotto
delle 18 CSK**, l'equivalente delle pagine EOWEB. Se la risoluzione azimutale
reale fosse 1.2 m invece di 1.0, i Δφ scenderebbero del 17% e due delle tre
CSK che passano uscirebbero dai gate.

**2. Il livello di prodotto delle CSK non è confermato.** Per TerraSAR-X è
`processingLevel: L0` su tutte e venti, esplicito: il grezzo. Per COSMO
l'offerta documentata parte da SCS (Level 1A), e col focalizzato dipendiamo da
ciò che il processore ha preservato della banda Doppler, invece di controllare
noi la partizione in sotto-aperture. **È il vantaggio strutturale più grande
del TerraSAR-X, e non si compensa con l'area di mare.**

Minori: l'area di mare COSMO è stimata come estensione al largo × 10.3 km di
azimut, quindi è un limite superiore; entrambe le costellazioni sono HH; le
soglie dei gate sono descrittive e non calibrate.

## Conseguenza per le due proposte

Restano entrambe, e diventano complementari invece che alternative.

**DLR / EOWEB**: Staring Spotlight, livello **L0**, priorità a 2020-09-07 e
2023-11-06 (boa dentro l'impronta, φ < 0.5°), più 2021-10-13 per la coppia con
la COSMO di quindici minuti prima.

**ASI Open Call for Science**: le CSK d'archivio 2020-09-08 e 2020-09-09 —
gratuite dentro l'80% da archivio — più il 20% di tasking in CSG Spotlight-2A,
che è l'unico modo COSMO con dwell adeguato (~4.1 s).

Prima di scrivere entrambe: recuperare i metadati di prodotto delle CSK e
girare il test su σ_Δφ. Il primo dice se le CSK reggono davvero i gate, il
secondo dice quanto conta il dwell rispetto all'area.
