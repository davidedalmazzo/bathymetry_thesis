# Block 17 — errata scientifico e implementativo

Questo documento non modifica retroattivamente i risultati congelati. Distingue ciò che resta valido da ciò che deve essere riformulato.

## Confermato

- Il baseline Block16A è riproducibile dallo snapshot archiviato: A=0, B=1, C=33, D=10106, E=0.
- Il filtro marino storico `ocean_fraction >= 0.80` era realmente applicato. L'ipotesi che fosse assente è quindi **smentita**.
- Il candidato long-dwell `collect:683a3778-7ef1-4653-bd9b-1777367585d5` resta C; non viene promosso.
- I quattro record NDBC archiviati hanno offset entro un'ora, ma il CSV conserva solo indicatori riassuntivi.

## Corretto nella nuova libreria

- La ricerca non si arresta più al primo download riuscito: vince la prima stazione ammissibile dopo ordinamento riproducibile per distanza e ID.
- `recovered`, validità temporale, completezza direzionale congiunta, uso per screening e riferimento indipendente sono stati separati.
- La completezza richiede densità, α1, α2, r1 e r2 validi **negli stessi bin** e copertura energetica congiunta della banda almeno pari alla soglia congelata.
- L'integrazione è una somma densità × larghezza-bin sui soli bin validi; non interpola attraverso missing.
- CPHD dwell e SICD processed aperture sono due budget distinti. Il numero ottenuto con `floor(duration/look)` è un conteggio nominale di aperture non sovrapposte, non una prova d'indipendenza statistica.
- `coast_distance_m_proxy` e `max_ocean_roi_diameter_m_proxy` sono rinominati concettualmente come clearance del punto rappresentativo e diametro centrato corrispondente. Il bordo limitante può essere costa **oppure bordo footprint**: non è il massimo ROI oceanico garantito.
- `competing_system_count` storico conta massimi locali e non sistemi ondosi fisici separati.

Inoltre, “bimodalità non dimostrata” non significa “un solo sistema certo”. I falsi sdoppiamenti di un controllo MEM non rendono artefatto ogni sdoppiamento reale; un confronto r2 con una sola famiglia unimodale non esclude ogni multimodalità; un test non significativo non prova assenza. I Block15G–J restano l'evidenza operativa sui limiti delle diagnostiche di miscela.

## Ritirato o declassato

- `2π/W` è una scala di Fourier legata al supporto, non un limite universale all'errore di uno stimatore parametrico.
- La larghezza fisica della banda non è l'incertezza dello stimatore della frequenza centrale.
- Un guadagno `sqrt(N_lobe)` non è utilizzabile senza un modello di covarianza tra bin/patch.
- L'incertezza batimetrica non può omettere la covarianza k–ω; il gradiente spaziale va proiettato lungo la propagazione.
- I conteggi di look precedentemente chiamati “independent” sono soltanto nominali finché la covarianza non è misurata.

## Limite di provenienza

La completezza congiunta per banda dei quattro spettri misurati non è ricostruibile dal CSV Block16A, perché gli array per-bin non furono archiviati. Il Block17 si astiene: non converte questa mancanza in “assenza di dato” e non cambia categorie. Gli hash di manifesti storici che precedono quarantene/correzioni Block14 descrivono lo stato dell'epoca; non vengono riscritti. Il manifest Block17 fotografa lo stato corrente.
