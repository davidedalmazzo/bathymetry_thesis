# Samoa — CHECKPOINT_28: preflight complesso

**B. Condizionato alla verifica del mapping Doppler–PVP nel PFA squintato e della leakage del supporto valido obliquo.** I metadati giustificano il percorso tecnico di una prima prova controllata, non una misura fisica già validata né un download automatico. Nessun confronto definitivo con altre zone.

## Identità, asset e durate

Collect `1424a3c8-7285-4210-b965-069514c13a2a`, `2025-03-31-21-51-37_UMBRA-09`, Umbra-09, spotlight monostatico right-looking, **H:H**. UUID SICD/STAC, core name SICD/CPHD e CollectStart coincidono; processing Umbra SAR Processor 5.0.20. Catalog datetime è il centro 21:51:37.8Z, non CollectStart 21:51:36Z. Il secondo differente nel basename non indica un'altra acquisizione.

| Quantità | Valore |
|---|---:|
| SICD pubblico, HEAD e FL NITF concordanti | 2.551.099.862 byte |
| CPHD pubblico, HEAD e listing concordanti | 25,234,138,880 byte |
| Durata catalogo | 3,6 s |
| SICD processed aperture, TEndProc−TStartProc | 2.975363044 s |
| SICD Timeline.CollectDuration | 3.700802707 s |
| SICD IPP span | 3.691918012 s |
| CPHD TxTime primo–ultimo | 3.691770699 s |

Il CPHD era omesso dall'inventario normalizzato STAC ma presente nel listing pubblico congelato; la discrepanza è documentata, senza modificare il catalogo congelato. Tre campioni TxTime non provano continuità dell'intera serie. NITF: soli header e DES XML esatti; nessun byte di image segment. CPHD: header/XML e tre TxTime da 8 byte; nessun support/signal array.

## Geometria: tre oggetti diversi

Incidenza SCP **20.19181°**, ROI **20.24789°** sulla superficie WGS84 HAE dichiarata.

| Asse/direzione | Bearing orientato | Scarto assiale rispetto alla banda boa |
|---|---:|---:|
| Vendor range proxy (away from sensor) | 240.27141° | 39.39338° |
| Grid.Row UVect, componente orizzontale ENU allo SCP | 240.27142° | 39.39338° |
| LOS locale sulla superficie ROI, verso sensore | 59.97365° | 39.09561° |
| Incremento Row a Col costante, push-forward sulla superficie ROI | 278.73391° | 77.85587° |

SCPCOA.AzimAng=60.27141° è verso sensore; Grid.Row orizzontale punta in senso opposto, dunque stesso asse modulo180. Il push-forward di coordinate immagine non è quella semplice proiezione ENU: in squint/PFA varia anche la geolocalizzazione trasversale. Per trasformare un vettore d'onda della FFT immagine occorre il Jacobiano completo e la sua trasformazione covariante/inversa trasposta, non una sola rotazione. L'allineamento fisico range per lo scattering va distinto dalla direzione di una linea a Col costante. Non si usa il valore più favorevole per scegliere una banda.

## ROI e supporto valido

ROI congelata 1500×1500 m, centro (-14.286579014933421, -170.56379591085346); contenuta nei corner SICD e nel GeoData.ValidData. Proiezione dell'intero bordo (33 campioni/lato) nel poligono ImageData.ValidData: **True**. Margine GeoData valido **493.72 m**, margine footprint SICD **1058.61 m**; margine nel piano immagine **184.77 m**, non confuso con distanza al suolo. Residuo massimo proiezione **0.000567 m**. Convergenza 9/33 campioni e sensibilità HAE=0 salvate.

Superficie nominale: HAE SCP=30.83738 m, WGS84 ellissoidale; HAE=0 è solo sensibilità geometrica, **non** quota marina o tidal datum accertati. Maschera costiera Natural Earth 1:10m resta preliminare. ValidData è fortemente obliquo: contenimento della ROI non garantisce uno strip rettangolare interamente valido su tutte le Col. Mantenere intera estensione azimutale prima della FFT e controllare esplicitamente leakage/guard regions e maschera. Nessun crop azimutale preventivo piccolo.

## Riferimento osservativo e anteprima

51209: coordinate storiche riusate (-14.273, -170.501), osservazione 2025-03-31T22:00:00+00:00, offset +502.2 s; distanza boa–ROI **6.933 km**. Banda invariata **0.07–0.075 Hz**, Tp=13.33333 s, propagazione **20.87804°** alla boa. Payload/hash, frequenze, larghezze, momenti e maschere riusati integralmente. Questa non è una misura della direzione nella ROI; nessuna Snell o reselezione.

Nessuna piccola anteprima ufficiale pubblica nel listing/STAC. GEC (~682 MB) e SIDD (~512 MB) non scaricati; overview di TIFF privato non dimostrata asset pubblico piccolo. **Struttura ondosa non valutabile**; nessun prodotto completo per supplire.

## Sottoaperture: poche opzioni, nominali

RGAZIM/SLANT, NumRows=13310, NumCols=23958, RE32F_IM32F; Row range axis0, Col Doppler axis1, Col.Sgn=−1: FFT forward/IFFT inverse. DeltaKCOAPoly costante zero, supporto Col 2396:21562, 19166 bin; weighting UNIFORM, nessuna deweighting SVA da trasferire da Vandenberg. Grid.TimeCOAPoly costante non assegna da sola tempi fisici alle bande; PFA e PVP disponibili per verifica rigorosa successiva.

| Piano | Look nominali | Overlap | Risoluzione Col al suolo approssimata |
|---|---|---|---|
| two_nonoverlap | 2 × 1.4 s | 0% | 1.072 m |
| three_nonoverlap | 3 × 0.95 s | 0% | 1.579 m |
| two_overlapping | 2 × 1.8 s | 50% | 0.833 m |

Sono piani prodotti dal codice esistente, non look formati. La PSF è stimata scalando la larghezza full-band per frazione conservata e Jacobiano locale; finestre smooth la allargano ancora. La risoluzione resta dell'ordine di 1–2 m rispetto alla ROI di 1500 m, ma questa non è una misura della visibilità delle onde. Nessun gate su un ciclo, dwell minimo o 45° di fase. Bande disgiunte non sono automaticamente repliche statisticamente indipendenti; look sovrapposti sono correlati. Tempi bandwidth/processed-aperture **nominali**, non PVP-validated; non stimata frequenza SAR.

## Budget, limiti e arresto

Nuova tranche distinta: **16/20 transazioni, 59642/20971520 byte**, massimo per risposta 5 MiB. Primo probe sandbox fallito e diagnosticato (proxy locale porta9); rete pubblica usata soltanto dopo approvazione del meccanismo di esecuzione autorizzato. Una richiesta METADATA JSON 404 è stata involontariamente ripetuta al resume tecnico per discovery CPHD: entrambi i tentativi sono conservati e conteggiati; il runner ora riusa anche i fallimenti 403/404. Range ignorati respinti prima della lettura del corpo.

Decisione **B**, non validazione: prima di interpretare fase servono mapping Doppler–PVP/PFA e controllo del supporto azimutale obliquo; esposizione/direzione boa–ROI e struttura ondosa rimangono condizionate. I metadati non motivano inversione o nuova frequenza reale. Nessun nuovo SAR completo, formazione, AIS, Block20, Vandenberg, commit o push. Nessun download automatico.
