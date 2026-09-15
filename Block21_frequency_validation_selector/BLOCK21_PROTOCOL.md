# Block21 — protocollo congelato del selettore per validazione della frequenza

## Identificatore e stato

`Block21` è il primo identificatore libero nel worktree: Block19 e Block20 sono
presenti. Block20 non viene auditato né usato. Commit iniziale
`3ebc9b9d61064f10a4db65906c66e5850412750d`; helper di push e cinque output
Block15 non tracciati preesistevano e restano esclusi.

## Obiettivo e separazione

Il risultato primario ordina scene per validare `fase intensity → frequenza`
contro un riferimento misurato. Il potenziale batimetrico è una colonna
descrittiva separata e non entra nella classificazione primaria. Vandenberg è
escluso. Nessun risultato Block15–20 viene sovrascritto.

## Disegno congelato prima dell'esecuzione

- Input: snapshot completo deduplicato Block16A `20260913T231747Z`, non una
  shortlist; varianti di processing preservate separatamente.
- Complesso utilizzabile: SICD oppure CPHD/BP; GEC/preview non bastano.
- Nessun gate su 15 s, cicli, periodo ≥10 s, `f≤0.1`, 80% acqua, profondità,
  `kh`, gradiente o shoaling.
- Configurazioni look prefissate `[1.5, 2.5, 4.0, 6.0] s`, calcolate
  separatamente su catalogo, SICD e CPHD. Conteggi non-overlap sono nominali;
  centri overlap non sono repliche indipendenti.
- ROI: griglia metrica locale deterministica 7×7 più representative point;
  quadrati `[250, 500, 750, 1000, 1500] m`, dal maggiore al minore. Si misura
  separatamente distanza dal footprint e dalla costa Natural Earth. La maschera
  è preliminare e non certifica pulizia SAR.
- Banda misurata: massimo di densità globale valido e lobo contiguo delimitato
  dai primi bin sotto metà picco; periodo, direzione circolare, concentrazione,
  larghezza ed energia provengono dallo stesso lobo. I massimi locali restano
  descrittivi.
- Ordinamento lessicografico/Pareto: riferimento, ROI/geometria, percorso
  complesso e metadati, fattibilità congiunta, costo. Nessun punteggio dwell o
  bonus manuale.
- Etichette nuove: `MEASURED_PRODUCT_CHECK`, `CONDITIONAL_REFERENCE_CHECK`,
  `MODEL_EXPLORATORY`, `EXCLUDED`, `NOT_EVALUABLE`; nessuna significa validato.

## Riferimenti e remoto

I quattro payload Block18 sono riusati offline. Dopo lo screening offline viene
congelata una coda di massimo 12 acquisizioni, al più due per stazione/località
comparabile. Per ciascuna si provano in ordine deterministico tutte le stazioni
attive entro 50 km; una risposta incompleta/fuori 3600 s non arresta la ricerca.
NDBC aggregato → annuale; CDIP solo con deployment verificato. Modelli sono
screening, non riferimento indipendente.

Budget remoto: 200 transazioni incluse redirect/retry, 100 MiB totali, 10 MiB
per risposta, timeout 45 s, massimo 2 retry. Limiti applicati durante streaming.
Una coda non coperta resta `not_queried`, mai `no_reference`.

## Arresto

Nessun crawl catalogo, download SAR, pixel SICD, signal CPHD, formazione, dwell
sweep, inversione o audit Block20. Stop dopo tabelle, schede 3–5 candidati,
test, report, summary e manifest. Nessun download successivo è automatico.

