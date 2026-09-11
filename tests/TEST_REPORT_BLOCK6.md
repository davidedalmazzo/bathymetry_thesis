# Test report — Block 6

Data esecuzione: 2026-08-31.

## Esito

- Suite Block 6: **9 passed** in 1.44 s.
- Suite compatibile con l’ambiente, inclusi i test regressivi dei blocchi precedenti: **21 passed** in 1.57 s.
- Il tentativo di raccolta dell’intera suite ha incontrato un solo limite ambientale: `tests/test_subaperture.py` importa `sarpy`, non installato nell’interprete `sdb-iride`. Il file è stato escluso dalla seconda esecuzione; non è un fallimento numerico del Blocco 6.

## Verifiche Block 6

- Segno cronologico numerico: `F_secondary * conj(F_reference)` recupera la pendenza imposta con il suo segno.
- Coppia hermitiana: le pendenze a `+k` e `-k` sono opposte.
- Filtro di coerenza: una patch decorrelata fra gli anchor indipendenti 1–6–11 viene esclusa.
- Formula quasi-lineare bidirezionale: la derivata analitica della fase coincide con la differenza finita.
- Il bin congelato riproduce esattamente `-0.3509722055168202 rad/s` e `T_SAR` non viene ricalcolato.
- La tabella contiene 68 righe, tutte con coerenza adiacente almeno 0.70, coerenza fra anchor almeno 0.25 e lunghezza d’onda 40–500 m.
- L’errore massimo di antisimmetria `s(k)+s(-k)` è inferiore a `2e-15 rad/s`.
- I campi obbligatori `kx`, `ky`, `|k|`, lunghezza d’onda, angoli, pendenza, errore, R² e coerenza sono presenti.
- Restano falsi i flag di dwell sweep, inversione batimetrica e retuning.

## Comandi

```powershell
$env:PYTHONPATH='code'
& 'C:\Users\ASUS\miniconda3\envs\sdb-iride\python.exe' -m pytest -q tests\test_phase_slope_map.py tests\test_block6_artifacts.py
& 'C:\Users\ASUS\miniconda3\envs\sdb-iride\python.exe' -m pytest -q --ignore=tests\test_subaperture.py
```

