# Block35 — selezione Sentinel-1 IW SLC su Duck

Protocollo fissato prima delle richieste e del confronto, 18 settembre 2026.
Esperimento preparatorio spaziale: k dal futuro SAR, omega esterna FRF con incertezza. Nessuna inversione, validazione temporale, scelta definitiva Spotlight/TOPS, pixel SAR o prodotto completo.

Primario CDSE OData ufficiale, ricerca pubblica anonima, attributi espansi e nextLink restituiti. Primo intervallo [2021-10-01T00:00:00Z,2021-11-01T00:00:00Z). Una sola estensione settembre–novembre possibile soltanto con motivazione persistita. Nessun fallback automatico dichiarato equivalente.

AOI WGS84 dichiarata: box lon [-75.751,-75.585], lat [36.165,36.265], comprende pontile, fascia FRF strumentata e transetto verso WR26. Area marina di screening separata, non supporto SAR valido né survey completo: lon [-75.740,-75.700], lat [36.175,36.200]. Nessuna ROI deriva dall'accordo con la profondità invertita.

Nuova tranche s1_duck_spatial_202110: massimo 80 HTTP / 150 MiB totali / 15 MiB per risposta. Registro creato prima della prima richiesta; retry/redirect/errori/byte parziali contati, niente reset/ampliamento. Riutilizzo soltanto di cache SHA256 verificate; budget storici invariati, consumo storico non determinabile. Documentazione ufficiale recuperata nella stessa tranche. Un solo writer, TLS verificato, niente aggiramento di restrizioni.

Passaggio A: parametri/QC delle onde e copertura temporale dei candidati del periodo, mediante proiezione mensile limitata a variabili scalari del client FRF, senza spettri; tutte le scene restano nella tabella. Passaggio B: massimo cinque acquisizioni, spettri/direzioni, vento/correnti/livello e metadati/rilievi pertinenti, stesso client e stessa tranche. Input nativi con ContentDate/Start come riferimento di catalogo, non centro fisico d'apertura.

Graduatoria senza score/pesi: livelli di evidenza separati (tecnica, riferimento, condizioni, incertezze). Per la rosa iniziale: disponibilità SLC/footprint, riferimento WR17 e AWAC contemporaneo con QC noto, assenza di duplicazioni della stessa acquisizione; poi spread nella banda di picco e Hs osservata come criteri descrittivi continui, non soglie fisiche. Mancanti non significano mare sfavorevole. Per la prima prova: completezza osservativa e supporto di survey/local geometry documentati prima di eventuale allineamento proxy. Parità dichiarata e risolta per timestamp crescente, non falsa precisione di score.

Direzione della banda misurata 'from' → propagazione +180°, confronto assiale modulo180. Nessuna correzione automatica. Bearing dei bordi del footprint è esclusivamente proxy. Nessuna incidenza38°, profondità boa→ROI, gradiente fisso, soglia Hs/L/kh/vento/cutoff/dwell/cicli/fase o 'pavimento Block17'. Sensibilità analitiche dispersione, non inversione del dato. Passo FFT, larghezza del lobo, incertezza dello stimatore e variabilità fisica restano distinti.

Survey: metadati e punti/linee effettivi, non bbox né primi N punti come copertura. ROI marine preliminari, supporto/burst/incidenza da verificare se annotazioni protette. Preview compressa non misura k e non dimostra presenza/assenza onde. Download ufficiale preparato ma non eseguito. Nessun commit/push.
