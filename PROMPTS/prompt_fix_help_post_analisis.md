# Fix puntual: `-help` debe funcionar en el prompt de guardar/corregir (post-análisis)

Proyecto grrux (repo `~/proyectos/ud2rrg`). Python: `./venv/bin/python`. NO hacer commits.
Fix QUIRÚRGICO de UX — nada más cambia.

## El bug (reproducido por Julian en uso real)

Tras analizar una oración, gruxx muestra el anuncio del glosario e inmediatamente el prompt de
guardado:

```
escribe "-help" para mostrar el glosario completo o "-help término" para buscar un término específico

¿Guardar en .txt? (s/n) — o (c) para corregir el análisis:  -help
```

…pero ESE prompt no acepta `-help`: lo ignora y salta al prompt siguiente
(`Oración (o 'salir'):`), que es el único que sí lo procesa. Es exactamente al revés de lo
útil: el momento en que el usuario acaba de ver terminología desconocida en un análisis es
cuando necesita el glosario — el anuncio se lo ofrece ahí y el input no lo honra.

## El fix

- El prompt de guardar/corregir (`¿Guardar en .txt? (s/n) — o (c)…`) debe aceptar
  `-help`/`--help`/`-ayuda`/`--ayuda` con o sin término: imprime el resultado del glosario
  (misma función existente de `glosario.py`) y **vuelve a mostrar el mismo prompt**, sin perder
  el análisis en pantalla ni el estado del flujo (se puede consultar el glosario varias veces y
  después guardar, corregir o pasar).
- Aplicar lo mismo a los demás sub-prompts del flujo post-análisis donde el usuario escribe
  texto (el menú de corrección y sus sub-menús): `-help [término]` responde y re-muestra el
  prompt actual. Regla general: en CUALQUIER input interactivo de gruxx, `-help` nunca debe
  tragarse ni abortar el flujo.
- No tocar el comportamiento ya correcto del prompt `Oración (o 'salir'):` ni del modo batch.

## Tests (fríos, input inyectado — patrón de test_l5)

1. Secuencia `-help agx` → glosario responde → re-prompt → `s` → guarda normal.
2. Secuencia `-help` (completo) → re-prompt → `n` → no guarda, flujo sigue.
3. Secuencia `-help zzz` → mensaje "no encontrado" → re-prompt → `c` → el menú de corrección
   abre normal.
4. Dentro del menú de corrección: `-help clase` responde y re-muestra el menú; `Esc` sigue
   cancelando limpio.
5. Regresión: `s`/`n`/`c`/Esc directos funcionan igual que antes; suites frías completas
   verdes.

Checkpoint: solo confirmar el fix con la transcripción de una sesión interactiva simulada
(análisis → `-help término` → `-help` → `s`).
