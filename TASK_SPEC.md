# Task Codex — Umbra Vandenberg SAR ocean-wave sub-aperture analysis

Stiamo lavorando a una tesi magistrale sulla possibilità di recuperare informazioni temporali delle onde marine da immagini SAR mediante sub-aperture / cross-spectra, con successiva applicazione alla batimetria.

Voglio che tu lavori come sviluppatore scientifico molto rigoroso: prima verifica dati, metadati, convenzioni e codice; poi implementa. Non assumere che gli script che ti fornisco siano corretti solo perché esistono già.

---

# 0. VINCOLO ASSOLUTO SUL FILESYSTEM

La root di lavoro è ESCLUSIVAMENTE:

`D:\Dati tesi\Umbra`

Devi considerare questa directory come l'unico workspace autorizzato.

## Regole obbligatorie

Puoi eseguire programmi/interpreti già installati nel sistema, ma:

* NON creare, modificare, cancellare o scaricare file fuori da `D:\Dati tesi\Umbra`.
* NON lavorare nel vecchio repository `C:\Tesi_final\...`.
* NON modificare alcun file su `C:`.
* NON installare pacchetti globalmente.
* NON utilizzare cartelle temporanee su `C:` se puoi evitarlo.
* NON creare un nuovo clone/repository altrove.
* NON spostare né cancellare i grandi file radar originali.
* I file originali CPHD/SICD devono essere trattati come READ-ONLY.

Se hai bisogno di un ambiente Python dedicato, crealo dentro:

`D:\Dati tesi\Umbra\.venv`

Imposta, quando possibile:

`TEMP=D:\Dati tesi\Umbra\_tmp`

`TMP=D:\Dati tesi\Umbra\_tmp`

`PIP_CACHE_DIR=D:\Dati tesi\Umbra\_cache\pip`

Se un file che ti fornisco tramite upload appare inizialmente fuori da `D:`, consideralo un input read-only: copialo nella struttura appropriata sotto `D:\Dati tesi\Umbra` e da quel momento lavora esclusivamente sulla copia in D:.

Se una determinata operazione richiedesse inevitabilmente una modifica permanente fuori da D:, NON eseguirla: segnalamelo.

All'inizio del lavoro stampa esplicitamente:

* current working directory;
* Python executable utilizzato;
* TEMP e TMP;
* spazio libero su D:;
* albero di primo livello di `D:\Dati tesi\Umbra`.

Poi fai:

`cd /d "D:\Dati tesi\Umbra"`

e resta lì.

---

# 1. DATASET PRINCIPALE

La scena Umbra che abbiamo selezionato è:

`2025-02-16-18-55-44_UMBRA-10`

sulla costa di Vandenberg / California.

Il CPHD dovrebbe trovarsi in:

`D:\Dati tesi\Umbra\Vandenberg\2025-02-16-18-55-44_UMBRA-10_CPHD.cphd`

Dimensione attesa del file completo:

`140554224768 byte`

Verifica localmente la dimensione prima di fare altro.

NON leggere sequenzialmente tutti i 140 GB per fare questa verifica.

Il CPHD deve essere conservato per le elaborazioni definitive e per controllare in futuro la relazione esatta tra slow-time, geometria e sub-aperture.

Abbiamo interesse anche al SICD complesso focalizzato della STESSA acquisizione, atteso dell'ordine di ~10–12 GB.

Il SICD servirà per sviluppare rapidamente la decomposizione in sub-aperture senza dover implementare subito un focalizzatore CPHD completo.

---

# 2. CONTESTO SCIENTIFICO DA TRATTARE COME IPOTESI DA VERIFICARE

Dalle analisi precedenti risultano indicativamente:

* dwell complessivo ≈ 22.6 s;
* incidence/graze geometry circa 21.9° di incidenza;
* viewing/range azimuth circa 105.85°;
* right-looking;
* ground-track circa 191.2°;
* asse azimutale circa 11.2°;
* swell durante l'acquisizione con periodo dell'ordine di 9–10 s;
* direzione dello swell apparentemente molto vicina all'asse di range secondo l'hindcast;
* un'analisi preliminare del GEC ha mostrato vicino costa un possibile picco spaziale attorno a 100 m.

ATTENZIONE:

queste NON sono verità da hardcodare.

Devono essere confrontate con i metadati effettivi del CPHD/SICD.

In particolare, il numero ~9.4–9.65 s proveniva da uno screening oceanografico e non va automaticamente chiamato `Tp` se la sorgente forniva il periodo medio dello swell.

Analogamente, il possibile picco a ~100 m osservato nel GEC è solo un indizio.

Il GEC NON è adeguato per l'analisi quantitativa finale perché:

* è un prodotto di ampiezza;
* è quantizzato/stretched;
* non conserva la fase complessa;
* può contenere effetti dovuti al processing ad apertura piena;
* alcuni controlli su terra mostravano anisotropie non trascurabili.

Quindi NON usare il GEC come ground truth.

---

# 3. OBIETTIVO GENERALE

Voglio verificare sperimentalmente come la possibilità di recuperare la dinamica delle onde dipenda dal tempo di apertura SAR.

L'idea centrale è sfruttare UNA SOLA acquisizione long-dwell da circa 22.6 s e generare sub-aperture equivalenti a tempi più corti, per esempio:

20 s
16 s
12 s
10 s
8 s
6 s
5 s

Questo permette di isolare l'effetto del dwell mantenendo invariati:

* mare;
* swell;
* batimetria;
* geometria SAR;
* sensore;
* incidenza;
* rumore ambientale.

Successivamente vogliamo arrivare a una relazione sperimentale del tipo:

`T_dwell -> qualità dei sub-look -> cross-spectrum -> coherence -> phase -> omega -> sigma_omega -> sigma_h`

Ma NON saltare direttamente all'inversione batimetrica.

La priorità adesso è ottenere una decomposizione sub-aperture fisicamente corretta e verificata.

---

# 4. FASE A — INVENTARIO E AUDIT

Prima di scrivere nuovo codice:

1. inventaria tutti i file presenti sotto:

`D:\Dati tesi\Umbra`

2. individua gli script che ti ho fornito, ad esempio se presenti:

* `cphd_probe.py`
* `gec_look.py`
* `sicd_subaperture.py`
* eventuali `.bat`
* README
* altri script Umbra

3. NON assumere che siano corretti.

Leggili integralmente e prepara:

`D:\Dati tesi\Umbra\AUDIT_CODE.md`

Per ogni script descrivi:

* cosa fa;
* input;
* output;
* ipotesi implicite;
* assi FFT utilizzati;
* convenzioni angolari;
* possibili errori;
* dipendenze;
* problemi di memoria;
* eventuali modifiche che proponi.

Non modificare subito gli originali.

Se serve una nuova versione, salvala sotto una directory tipo:

`D:\Dati tesi\Umbra\code\`

---

# 5. FASE B — VERIFICA CPHD LEGGERA

Sul CPHD da 140 GB NON fare ancora processamento massivo.

Leggi soltanto:

* header ASCII;
* XML metadata;
* eventuali piccoli blocchi necessari.

Voglio ottenere dal file reale, se disponibili:

* CollectStart;
* CollectDuration;
* numero di channels;
* NumVectors;
* NumSamples;
* dominio CPHD;
* TxTime min/max;
* PRF o equivalente;
* bandwidth;
* center frequency;
* polarization;
* platform;
* Tx/Rcv geometry;
* PVP fields disponibili;
* SRP;
* SideOfTrack;
* dwell effettivo derivabile dai tempi.

Confronta il dwell ricavato dal file con ~22.6 s.

Salva un report in:

`D:\Dati tesi\Umbra\Vandenberg\metadata\CPHD_REPORT.md`

e, se utile:

`CPHD_METADATA.json`

NON leggere l'intero signal array.

---

# 6. FASE C — SICD

Controlla se esiste già il SICD della stessa acquisizione nella cartella Vandenberg.

Se NON esiste:

1. verifica tramite listing/catalogo Umbra il nome ESATTO dell'asset;
2. verifica `Content-Length`;
3. assicurati che appartenga esattamente al collect
   `2025-02-16-18-55-44_UMBRA-10`;
4. scaricalo ESCLUSIVAMENTE in:

`D:\Dati tesi\Umbra\Vandenberg\`

usando un download riprendibile (`curl -C -` o equivalente).

NON riscaricare il CPHD.

NON scaricare altri dataset di grandi dimensioni.

Per nuovi download superiori a 20 GB diversi da questo SICD, fermati prima e segnalamelo.

---

# 7. AMBIENTE PYTHON

Preferisco SarPy per leggere SICD/NITF.

Se SarPy non è disponibile, crea un virtual environment sotto D:.

NON fare `pip install` globale.

Registra in:

`D:\Dati tesi\Umbra\ENVIRONMENT.md`

almeno:

* Python executable;
* Python version;
* NumPy version;
* SciPy version se usata;
* SarPy version;
* Matplotlib version;
* altri pacchetti rilevanti.

---

# 8. FASE D — ISPEZIONE SICD

Prima di qualsiasi decomposizione, leggi i metadati SICD e genera:

`D:\Dati tesi\Umbra\Vandenberg\metadata\SICD_REPORT.md`

Voglio vedere almeno:

## ImageData

* NumRows
* NumCols
* PixelType

## Grid

* Grid.Type
* Grid.ImagePlane
* Row.SS
* Col.SS
* Row.ImpRespBW
* Col.ImpRespBW
* Row.DeltaK1 / DeltaK2
* Col.DeltaK1 / DeltaK2
* DeltaKCOAPoly se presente

## Timeline

* CollectStart
* CollectDuration
* IPP information se disponibile

## ImageFormation

* ImageFormAlgo
* TStartProc
* TEndProc
* TxFrequencyProc
* processing polarization

## SCPCOA

* SCPTime
* SlantRange
* GroundRange
* GrazeAng
* IncidenceAng
* AzimAng
* SideOfTrack
* DopplerConeAng

## Position / GeoData

coordinate SCP e informazioni necessarie per geolocazione.

Confronta poi quantitativamente i valori del SICD con quelli del CPHD.

---

# 9. QUESTIONE CRITICA: QUALE ASSE È AZIMUTH?

NON assumere automaticamente `axis=0` o `axis=1`.

Determina dai metadati reali SICD e dalle convenzioni SarPy quale dimensione dell'array corrisponde:

* range;
* azimuth / cross-range / Doppler.

Se `Grid.Type = RGAZIM`, verifica esplicitamente la convenzione Row/Col.

Scrivi la conclusione nel report.

Qualunque funzione di decomposizione deve ricevere o determinare esplicitamente l'asse FFT e deve rifiutarsi di procedere se la geometria non è chiara.

---

# 10. PRINCIPIO DELLA DECOMPOSIZIONE SUB-APERTURE

Il SICD è già focalizzato.

L'approccio che vogliamo testare è dividere la banda Doppler azimutale dell'immagine complessa in sotto-bande e rifare l'IFFT per ottenere sub-look associati a porzioni differenti dell'apertura.

La pipeline concettuale deve essere:

`complex SICD -> FFT lungo azimuth -> selezione Doppler -> IFFT -> complex sub-look`

La fase complessa deve essere preservata.

NON trasformare in intensità prima di aver formato i sub-look complessi.

---

# 11. ATTENZIONE ALLA ROI: NON TAGLIARE L'AZIMUTH PRIMA DELLA FFT SENZA VERIFICA

Questo è importante.

Se tagli una piccola ROI nella direzione azimutale PRIMA della FFT, stai moltiplicando il segnale per una finestra spaziale e quindi convolvendo/allargando lo spettro Doppler.

Questo può contaminare proprio la decomposizione che vogliamo studiare.

Quindi preferisco:

* leggere una STRISCIA limitata in range;
* mantenere, quando possibile, tutta o una grande parte dell'estensione azimutale;
* fare la decomposizione Doppler;
* SOLO DOPO ritagliare la ROI azimutale di interesse.

Se per ragioni di RAM devi limitare anche l'azimuth prima della FFT:

* quantifica l'effetto;
* usa una guard region molto ampia;
* confronta almeno due estensioni azimutali diverse;
* non interpretare risultati scientifici finché la stabilità non è verificata.

Implementa processamento a chunk in range se necessario.

NON creare copie full-scene dei sub-look se non strettamente necessario.

---

# 12. DUE ESPERIMENTI DISTINTI

Non confondere questi due concetti.

## A. Reduced-aperture image

Per simulare qualitativamente una minore apertura possiamo prendere una porzione centrata della banda Doppler equivalente a una frazione:

`f = T_sub / T_full`

come prima approssimazione.

Questo serve a vedere come cambia l'immagine con:

20, 16, 12, 10, 8, 6, 5 s.

## B. Multi-look temporal experiment

Per recuperare la dinamica dell'onda servono invece almeno due sub-look con centri di apertura differenti.

Quindi implementa la possibilità di definire:

* larghezza sub-apertura;
* posizione/centro della sub-apertura;
* overlap;
* tempo nominale associato al centro.

Per esempio con `T_full ~= 22.6 s` e aperture da 6 s possiamo avere più look differenti distribuiti lungo l'apertura.

NON limitarti a produrre una singola sub-apertura centrata da 6 s.

---

# 13. IMPORTANTE: DOPPLER FRACTION NON È ANCORA TEMPO ESATTO

Per la prima dimostrazione possiamo usare approssimativamente:

`bandwidth_fraction ~= T_sub / T_full`

ma NON voglio che questo venga presentato nella tesi come una relazione esatta senza validazione.

Nello spotlight SAR la relazione fra:

* slow time;
* look angle;
* Doppler centroid;
* posizione nella banda Doppler

deve essere verificata dalla geometria reale.

Quindi:

* chiama i tempi derivati dal semplice rapporto di banda `nominal` o `approximate`;
* NON etichettarli come exact;
* prepara il codice in modo che in seguito sia possibile sostituire questa approssimazione con una mappatura derivata dal CPHD/PVP.

Una futura fase dovrà utilizzare il CPHD per determinare la relazione fisica più rigorosa tra sub-aperture e tempo.

---

# 14. WINDOWING E NORMALIZZAZIONE

Implementa almeno due possibilità:

* rectangular Doppler window;
* smooth window, preferibilmente Tukey / raised-cosine.

Documenta:

* larghezza nominale;
* equivalent noise bandwidth;
* normalizzazione energetica;
* eventuale perdita di risoluzione;
* ringing.

Ogni sub-look deve avere metadata associati, per esempio JSON, con:

* Doppler support;
* normalized bandwidth fraction;
* nominal dwell;
* center fraction;
* window;
* effective bandwidth;
* FFT axis;
* original SICD identifier.

---

# 15. TEST NUMERICI OBBLIGATORI

Prima dei dati reali crea test sintetici.

Voglio almeno:

### FFT/IFFT

Verifica round-trip numerico.

Errore relativo atteso vicino alla precisione floating point.

### Split/recombine

Con finestre rettangolari disgiunte che coprono tutta la banda, la somma dei sub-look deve ricostruire il segnale originale entro l'errore numerico, tenendo conto della convenzione FFT adottata.

### Axis test

Costruisci un segnale sintetico la cui modulazione sia nota lungo una sola dimensione e verifica che lo splitter agisca sull'asse giusto.

### Band-location test

Una sinusoide a frequenza Doppler nota deve finire nella sotto-banda prevista.

### Cross-spectrum synthetic test

Crea due immagini sintetiche contenenti un'onda spaziale con fase nota:

`I2(x,y) = I1(x,y)` con uno shift di fase noto della componente ondosa.

Verifica che il cross-spectrum recuperi il segno e la fase corretta.

Salva i test sotto:

`D:\Dati tesi\Umbra\tests\`

e produci un report:

`TEST_REPORT.md`

---

# 16. CROSS-SPECTRUM: NON ASSUMERE LA FORMULAZIONE

Prima di implementare il retrieval scientifico definitivo verifica quale oggetto vada realmente usato nel metodo ocean-wave SAR:

* cross-spectrum delle immagini complesse;
  oppure
* cross-spectrum delle INTENSITY images ricavate dai sub-look complessi.

Non assumere che siano equivalenti.

Per la letteratura oceanografica SAR è probabile che la procedura rilevante utilizzi sub-look intensity images, ma voglio che tu lo verifichi contro una fonte primaria / paper o formulazione teorica affidabile prima di fissare l'algoritmo.

Nel codice mantieni comunque i sub-look complessi fino a quel punto.

Documenta chiaramente la scelta.

---

# 17. COREGISTRAZIONE E FASE DETERMINISTICA

Prima di interpretare la fase del cross-spectrum come dinamica dell'onda, verifica se sub-look provenienti da differenti centri Doppler presentano:

* shift azimutale;
* shift range;
* phase ramp;
* differenze geometriche deterministicamente previste;
* decorrelazione dovuta a differente look angle.

Utilizza una zona di TERRA stabile della stessa scena come controllo, se disponibile.

L'obiettivo è separare:

`phase due to processing/geometry`

da

`phase associated with ocean-wave evolution`.

Se una fase o shift simile compare anche sulla terra, NON interpretarlo come dinamica marina.

Implementa se necessario:

* registration via phase correlation;
* subpixel shift estimation;
* linear phase ramp estimation/removal.

Ma non rimuovere termini senza documentarli.

---

# 18. ROI SCIENTIFICHE

Non scegliere automaticamente la ROI definitiva.

Per la prima esplorazione identifica almeno:

* una zona nearshore ocean;
* una zona offshore ocean;
* una zona land control.

Salva coordinate pixel e, se possibile, coordinate geografiche.

Le ROI devono essere riproducibili tramite file JSON/YAML, non selezionate solo manualmente.

Esempio:

`D:\Dati tesi\Umbra\Vandenberg\roi\rois.json`

---

# 19. PRIMO ESPERIMENTO REALE

Dopo avere completato audit, metadata inspection e test sintetici:

esegui una PRIMA elaborazione piccola e controllata.

Obiettivo:

sub-aperture nominali da circa 6 s.

NON produrre subito tutte le combinazioni possibili.

Voglio prima verificare che:

* l'orientamento sia corretto;
* i sub-look mostrino la stessa costa;
* la fase sia preservata;
* non vi siano flip/transpose;
* il comportamento su terra sia sensato;
* il contenuto oceanico non sia dominato da artefatti.

Produci figure diagnostiche:

* full-aperture intensity;
* sub-look intensities;
* difference images;
* coherence;
* eventuale cross-spectrum preliminare;
* Doppler windows usate.

Le figure vanno in:

`D:\Dati tesi\Umbra\Vandenberg\results\diagnostics\`

---

# 20. SOLO DOPO: DWELL SWEEP

Se il test da 6 s è valido, prepara l'esperimento:

20, 16, 12, 10, 8, 6, 5 s.

Non necessariamente devi eseguirlo tutto immediatamente: prima crea una pipeline riproducibile.

Per ciascun dwell voglio poter misurare in futuro:

* spatial wave peak;
* coherence;
* cross-spectral phase;
* phase uncertainty;
* omega estimate;
* dispersion across independent sub-look pairs;
* eventuale retrieval di depth.

---

# 21. OUTPUT E SPAZIO DISCO

Evita di produrre centinaia di GB di copie.

Preferisci:

* processing a chunk;
* ROI complex64;
* `.npy` / `.npz` piccoli;
* metadata JSON;
* PNG solo diagnostici.

Prima di creare un singolo output >10 GB, fermati e valuta se è davvero necessario.

Non duplicare il SICD o il CPHD.

Non cancellare mai originali.

---

# 22. RIPRODUCIBILITÀ

Crea:

`D:\Dati tesi\Umbra\WORKLOG.md`

Aggiornalo durante il lavoro con:

* timestamp;
* comando eseguito;
* file input;
* file output;
* risultato;
* eventuali errori;
* decisioni metodologiche.

Crea inoltre una struttura ordinata, per esempio:

`D:\Dati tesi\Umbra\code`

`D:\Dati tesi\Umbra\tests`

`D:\Dati tesi\Umbra\Vandenberg\metadata`

`D:\Dati tesi\Umbra\Vandenberg\roi`

`D:\Dati tesi\Umbra\Vandenberg\results`

`D:\Dati tesi\Umbra\Vandenberg\results\diagnostics`

`D:\Dati tesi\Umbra\_tmp`

Non creare directory fuori dalla root autorizzata.

---

# 23. STILE DI LAVORO

Voglio che tu faccia ricerca e debugging in autonomia.

Non chiedermi conferma per ogni piccolo passaggio.

Se trovi un bug, correggilo e documentalo.

Se una mia ipotesi scientifica è sbagliata, dimmelo chiaramente.

Non cercare di far “funzionare” a tutti i costi il risultato atteso.

Se l'onda a ~100 m osservata nel GEC non appare nel SICD correttamente elaborato, questo è un risultato da riportare, non un errore da nascondere.

Distingui sempre fra:

* dato misurato;
* metadata;
* assunzione;
* approssimazione;
* risultato numerico;
* interpretazione fisica.

---

# 24. PRIMO CHECKPOINT CHE VOGLIO DA TE

Prima di partire con elaborazioni pesanti, restituiscimi un riepilogo contenente:

1. contenuto rilevante trovato sotto `D:\Dati tesi\Umbra`;
2. conferma che NON hai scritto nulla fuori da D:;
3. dimensione e stato del CPHD;
4. presenza/stato del SICD;
5. audit preliminare degli script caricati;
6. interprete Python e ambiente utilizzato;
7. metadati principali CPHD;
8. metadati principali SICD, se disponibile;
9. determinazione inequivocabile dell'asse range e dell'asse azimuth;
10. eventuali problemi scientifici o software trovati;
11. piano concreto per il primo test sub-aperture da ~6 s.

Dopo questo checkpoint puoi proseguire autonomamente con i test sintetici e il primo esperimento leggero, purché non richieda nuovi download >20 GB o output singoli >10 GB.

La priorità è CORRETTEZZA SCIENTIFICA + RIPRODUCIBILITÀ, non velocità a tutti i costi.
