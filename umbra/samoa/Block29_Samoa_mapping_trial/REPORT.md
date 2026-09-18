# CHECKPOINT_29 — Samoa: mapping gate e arresto tecnico

**Gate A: CONDITIONAL. SICD non scaricato.**
Non si è ottenuta un'associazione globale/locale sufficientemente verificata per assegnare tempi fisici unici alle sotto-bande della prova sulla ROI. Non viene avviato un diverso percorso di formazione. Non è una dichiarazione che la scena o il metodo siano fisicamente inutilizzabili.

## 1. Mapping verificato e limiti

Intero blocco PVP: **21716 vettori**, **376 byte/vettore**, layout XML SarPy big-endian con interi SIGNAL/PulseNumber distinti dai float. TxTime/RcvTime e scena-interaction time monotoni. dt mediano 0.000169994667 s, massimo/mediana 1.005428; SIGNAL={1}, nessun campionamento parziale della continuità.

TxTime span **3.691770699 s**, distinto dall'apertura SICD processata **2.975363044 s** e catalogo 3,6 s. Scene time è la media di TxTime+R_tx/c e RcvTime−R_rx/c; chiusura massima dei due cammini 8.545e-09 s. La differenza Tx/scene time (~2 ms) non è confusa con durata processata.

Geometria primaria: somma dei versori bistatici sensore→punto, divisa per c, proiettata lungo FPN sul piano IPN. k [cycles/m]=f[Hz]×coefficiente. Questa proiezione di focus-plane è diversa dalla semplice LOS·Grid.Col usata in uno sviluppo precedente; quest'ultima non viene trasferita a Samoa senza verifica PFA. Angolo atan2(k_col,k_row), non frazione bandwidth=frazione tempo. Residuo equivalente temporale massimo PVP vs PolarAngPoly **1.082e-08 s**, ARP SICD vs PVP **3.536e-07 s**.

Il mapping geometrico **allo SCP è coerente**. Per il kernel di una banda Col, però, theta=atan2(k_col,k_row): si integra sull'intera banda Row, non esiste automaticamente un solo tempo per Col. Uniform-output-k e uniform-time sono due pesi geometrici dichiarati. UNIFORM SICD non dimostra pesi di illuminazione originali uniformi; interpolazione e pulse weighting del fornitore non sono integralmente ricostruiti. Nessun kernel detto esatto.

## 2. Gate prefissato

CONFIG salvata prima di recuperare i PVP, SHA256 `5b264e836dc1b6dbe93d4ac114be01fe0d94f9228c40faac173bdc86a2330c7c`. Limiti: centro 0,05 s; sensibilità baseline 5%; durata 10%; coerenza geometria/polinomi 0,01 s. Il limite baseline controlla direttamente l'errore di scala della pendenza. Non sono derivati dal Tp della boa né rilassati dopo i risultati.

Massima variazione dei centri nei controlli **0.392281 s**; baseline **4.581%**; durata **4.592%**. Kernel non identificabili nel controllo locale **19/90**. Esito dei check: `{"ARP_geometry_timing": true, "PFA_angle_monotone": true, "all_candidate_kernels_identifiable": false, "baseline_sensitivity": true, "center_sensitivity": false, "duration_sensitivity": true, "frequency_support": false, "poly_geometry_timing": true, "processed_support": false, "temporal_continuity": true}`.

Separazione dei contributi: sola dipendenza Row allo SCP **0.037861 s**; offset del solo gradiente locale ROI al carrier centrale **0.357570 s**; uniforme-k contro uniforme-tempo **0.000888 s**. Lo scale factor PFA ricostruito dalla geometria concorda con SpatialFreqSFPoly entro **3.146e-10**. ETag CPHD multipart concordante con listing congelato; non interpretato come MD5.

**Cautela importante:** le coordinate di output PFA sono globali e comuni all'immagine. Riproiettare il gradiente locale a un punto ROI non equivale a reindicizzare automaticamente quel reticolo. Lo shift locale di 0,392 s può contenere termini deterministici di focalizzazione/carrier che andrebbero trasportati correttamente prima di chiamarlo bias temporale fisico. Questo blocco identifica un impedimento di modellazione, non prova un bias oceanico di tale ampiezza. Per la stessa ragione i casi locali fuori supporto non dimostrano pixel SICD invalidi. Non si estrapolano kernel o si cambiano bande per far passare il gate.

I tempi geometrici SCP per i piani candidati sono conservati in BAND_TIMES.csv; le dipendenze Row/posizione e i casi non identificabili sono espliciti. La primaria a tre bande e il controllo a due bande sono quelli prefissati da Block28; non sono stati formati look reali. Nessuna linearità da una sola coppia, nessuna falsa indipendenza dei look.

Al carrier Row centrale i tre centri geometrici SCP sono circa 3,126629 / 2,216655 / 1,302203 s dall'inizio collezione per indici banda 0/1/2: **ordine temporale inverso rispetto alla frequenza Col crescente**. Durate del supporto circa 0,907747 / 0,912207 / 0,916702 s, non automaticamente i 0,95 s nominali. Il test di cronologia e quelli FFT/coniugati verificano numericamente i segni, senza inferirli solo da Col.Sgn.

## 3. Geometria e supporto

LOS fisica, proiezione orizzontale Grid.Row e push-forward delle coordinate a terra restano distinti come in Block28. Jacobiano completo [m EN/m RowCol immagine] in WAVEVECTOR_TRANSFORM.json; k_ground[rad/m]=J^(-T)k_image[rad/m]. Nessuna rotazione semplice. ROI congelata e ValidData obliquo invariati; contenimento metadata non sostituisce controllo dei pixel reali.

Piccolo sintetico complex **nel dominio immagine**, maschera con vertici del SICD scalati, carrier separati e intensità con fase nota: caso statico e dinamico a −0,7 rad/s di verità sintetica arbitraria, non spettro boa. Un trattamento hard-mask esplicito e una sola variante taper a 8 pixel; full Col prima della FFT. Coefficienti, fasi/residui e differenze salvati; non viene chiamato simulatore fisico SAR o controllo della leakage del dato reale. Nessuna sottrazione di pendenza sintetica al mare.

Nel sintetico statico le pendenze sono numericamente zero (~10^-16 rad/s); nel caso dinamico, riferimento −0,7 rad/s, hard-mask −0,7003363 e unica variante taper −0,6999604 rad/s. Questi scostamenti sono diagnostici del piccolo modello imposto, non intervalli di confidenza né una certificazione del supporto reale. Non determinano il gate temporale e non compensano il mancato controllo globale/locale.

## 4. Prova reale non eseguita

Integrità SICD completa e SHA256: **non valutabili, download non iniziato**. Identità/dimensioni metadata restano quelle verificate Block28 (SICD 2.551.099.862 byte, CPHD 25.234.138.880 byte, HH). Struttura ondosa e controllo terrestre: **non osservati**. Leakage reale, fase reale e stabilità di pendenze: **non misurate**. Non vengono inferite dalle simulazioni. Interpretazione fisica e batimetrica non dimostrate; nessun q, confronto ottimizzato alla boa, dwell sweep o Vandenberg.

## 5. Budget, hash e riproducibilità

Fase A: **3/60 transazioni HTTP, 8165216/104857600 byte**; massimo 10 MiB/risposta. Primo probe sandbox rifiutato, diagnosticato; solo rete pubblica tramite esecuzione autorizzata. Range intero PVP verificato prima della lettura; fine blocco precedente al signal array. Retry automatici zero. SHA256 PVP `fab41f82c904d8794595c261708942cd6015274bedc414e465c9ded3ca26c0f9`. Registri fase A/B separati; fase B zero traffico e intermedi entro budget. Hash degli input congelati verificati senza riscriverli. Suite completa riportata nel TEST_REPORT, non dedotta da suite storiche.

**Un solo prossimo passo:** chiarire il trasporto dei kernel fra reticolo PFA globale e gradiente locale ROI, includendo la dipendenza Row, prima di autorizzare attraverso un nuovo gate la prova SICD. Nessun percorso alternativo di formazione viene avviato automaticamente.
