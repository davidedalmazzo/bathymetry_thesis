# Block27 — rappresentatività boa–ROI: checkpoint tranche autorizzata

## Budget e storia

**Consumo storico non determinabile**: transazioni e byte storici sono null, non zero.
La ricerca nei registri del blocco e nelle cache ha trovato archivi locali CDIP, ma nessun registro attribuibile completo alla fase precedente. Il nuovo registro è stato salvato prima della prima richiesta e i contatori persistiti prima di ogni transazione e durante lo streaming.
Questa tranche sostituisce per la prosecuzione il residuo sconosciuto; **non si dichiara rispettato il vecchio limite cumulativo**.
Nuova tranche: **30/30 transazioni HTTP, 1183903 / 20971520 byte**. Retry automatici zero; redirect conteggiati. I 13 tentativi sandbox con proxy rifiutato sono inclusi. Il cambio di trasporto autorizzato costituisce nuova informazione diagnostica, non un retry cieco. Nessun URL fallito nello stesso contesto è stato ripetuto.

## Osservazioni recuperate

- Samoa, 2025-03-31-21-51-37_UMBRA-09: spettro completo 51209, 64 frequenze; Tp=13.33333 s, banda half-power 0.07–0.075 Hz, propagazione 20.878°, offset 502.2 s. Densità e quattro momenti/direzioni con maschere individuali/congiunte; timestamp restituito dal server verificato. Asse range preliminare vendor: scarto assiale 39.393°, non verifica SICD locale. Candidato **condizionato**, non promosso tramite descrizioni generiche del sito.
- Louisiana: riuso integrale dei quattro payload **42084** Block18 (392 bin) verificati; nessuna richiesta per quei dati. **42094 è ancora non verificata alle date SAR**. I prodotti CDIP 246 locali coprono settembre–novembre **2019**, fuori dalle date 2025–2026 della coda; il sensore DWR-M3 d02 non viene attribuito alle date nuove.
- Tobago 42087: percorsi NDBC aggregate/2024 non disponibili (404). Pagina NDBC documenta ICON, buoy/anemometro e archivio meteorologico 2016, non spettri ondosi 2024. Fonte operator coral.noaa.gov fallita per timeout; alternativa AOML interrogata entro budget. Nessuna deduzione da “Buccoo Reef”, nessuna dichiarazione globale di assenza di onde o prodotti.
- Isole Vergini 41052: percorsi spettrali NDBC aggregate/2025 404; pagina di stazione recuperata. Strumentazione e serie spettrale all'evento non ancora stabilite. Il solo intervallo storico di posizione non certifica attività continuativa.

Stati per tutte le 23 acquisizioni: `{"recovered": 1, "request_failed": 18, "verified_local_Block18": 4}`. Cinque riferimenti utilizzabili (uno nuovo e quattro locali), **18 acquisizioni senza riferimento per-bin stabilito**. Le date della coda non sono state selezionate in base al mare. I 404 sono errori dei percorsi provati; eventuali archivi alternativi rimangono non interrogati, non “assenti”.

## Geografia

Riconciliazione locale precedente preservata e non rieseguita. Mappe aggiornate con ROI/footprint, stazioni effettive, distanze/rilevamenti, nord e scala. Tobago: segmento boa–ROI attraversa terra nella maschera Natural Earth 1:10m per circa 4.2–4.8 km. È un indizio di esposizione diversa, non prova che le onde non raggiungano i due punti. Il subset di costa OSM richiesto è fallito (504); verifica con costa adeguata ancora incompleta. Non-intersezione negli altri siti non prova mare uguale. Quote GEBCO della coda non usate per Snell né trasferimento automatico della direzione.

## Modelli

Documentazione [Open-Meteo marine](https://open-meteo.com/en/docs/marine-weather-api) recuperata: MFWAM globale 0.08°/3 ore da ottobre 2021; ERA5-ocean globale 0.5°/ora dal 1940; SMOC correnti 0.08°/ora da gennaio 2022. Queste disponibilità pubblicate coprono nominalmente le date, **non certificano ancora il recupero effettivo dell'evento**. Variabili/partizioni dipendono dal modello; periodo swell medio distinto dal peak. Maschera, indici/celle native, accoppiamento correnti e assimilazione delle stesse boe non verificati. Nessun subset di evento disponibile prima dell'esaurimento del budget, nessun confronto boa–ROI, nessuna mappa di celle inventata o climatologia sostitutiva.

## Decisione e arresto

Quantità di evidenza diversa fra zone: Samoa e quattro scene Louisiana condizionate; Tobago, Isole Vergini e altre 14 Louisiana non valutabili osservativamente. Nessuna priorità definitiva giustificata; nessun nuovo gate Hm0, kh, lunghezze d'onda, fase o distanza. Cinque payload riparsati offline identici con hash verificati. Stato riprendibile, log completo e manifest sotto questa versione; versione v1 e blocchi congelati intatti.

**Un solo prossimo passo:** recupero mirato dei riferimenti alternativi per le 18 scene senza spettri, a partire dalle stazioni e date della coda congelata, solo con un eventuale nuovo budget autorizzato. Nessun SAR, AIS, inversione, dwell sweep o Vandenberg.
