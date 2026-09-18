# Nota di pubblicazione del riordino

Il controllo pre-commit ha individuato cache storiche già tracciate, incluse nello staging dagli spostamenti precedenti. Conformemente ad AGENTS.md sono rimosse soltanto dall'indice Git del nuovo layout: i file sotto `umbra/selezione_scene/Block16_scene_selection/cache/` restano intatti sul disco ed esclusi da `.gitignore`.

Le versioni precedentemente pubblicate restano nella cronologia Git; non è stata riscritta la storia. Nessun payload locale è cancellato né modificato. Il manifest del riordino descrive il precedente snapshot verificato; questa nota registra separatamente la scelta di pubblicazione. Gli audit SHA-256 locali e i percorsi della mappa non vengono alterati per simulare disponibilità delle cache in un clone pubblico.
