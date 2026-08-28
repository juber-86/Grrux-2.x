# Checkpoint — Fase LINKING, Etapa L2.5 (Estructuras Lógicas ditransitivas)

Implementado según `prompt_linking_L2_5_ditransitivas.md`. **PARAR aquí** — L3
(capa `es` en `ud2rrg.py`) y L4 (checker de completeness + KPI-después)
esperan esta revisión.

Código nuevo: `aspect_classifier/ditransitivas.py` + `test_ditransitivas.py`
+ `data/verbos_ditransitivos.xlsx` (semilla, 54 verbos). Modificado:
`rrg_ls_mapper.py` (integración, ANTES de causatividad/wrappers),
`misc_rrg.py` (clave `RRGThemRel`), `config.yaml` (sección `ditransitivas`).
**`gruxx_ai1.py` NO se tocó** (el dict del mapper ya fluye por el render y
el MISC existentes, como anticipaba el prompt). Suites verdes fast+slow:
nucleo_periferia 10, pruebas_estructurales 25, wrappers_ls 22, misc_rrg 19,
ditransitivas 18, causatividad 9, pruebas_aspectuales 11, complejo 6,
fase2_contextual 8 — **128 tests, todos verdes**. Prohibiciones respetadas
(`ud2rrg.py`, clasificador, corroborador MLM, `pruebas_estructurales.py`,
`.joblib`, `contextual_sentences.csv` intactos, verificado por mtime).

## 1. Batería ditransitiva — EL nuevas

Las 6 frases exigidas por el prompt + 9 variadas (incluye los 2 verbos
ambiguos conocidos, `escribir` y `traer`, para mostrar el log en acción):

| Frase | Plantilla | Fuente | Amb. | LS léxica |
|---|---|---|---|---|
| Juan le dio un regalo a María | transferencia | léxico | — | `[do'(Juan, Ø)] CAUSE [BECOME have'(María, regalo)]` |
| Juan le compró un regalo a María | benefactiva | léxico | — | `[[do'(Juan, Ø)] CAUSE [BECOME have'(Juan, regalo)]] PURP [have'(María, regalo)]` |
| compró un regalo para María | benefactiva | léxico | — | `[[do'(3sg, Ø)] CAUSE [BECOME have'(3sg, regalo)]] PURP [have'(María, regalo)]` |
| compró un regalo | *(sin disparo — transitiva normal)* | | | |
| Le dije la verdad | comunicacion | léxico | — | `do'(1sg, [decir.to.(3sg)'(1sg, verdad)])` |
| le dije que viniera | comunicacion | léxico | — | `do'(1sg, [decir.to.(3sg)'(1sg, viniera)])` |
| María le regaló un libro a su hermano | transferencia | léxico | — | `[do'(María, Ø)] CAUSE [BECOME have'(hermano, libro)]` |
| El jefe le pagó el sueldo a Juan | transferencia | léxico | — | `[do'(jefe, Ø)] CAUSE [BECOME have'(Juan, sueldo)]` |
| Ana le hizo un pastel a su hija | benefactiva | léxico | — | `[[do'(Ana, Ø)] CAUSE [BECOME have'(Ana, pastel)]] PURP [have'(hija, pastel)]` |
| Los padres le construyeron una casa a su hijo | benefactiva | léxico | — | `[[do'(padres, Ø)] CAUSE [BECOME have'(padres, casa)]] PURP [have'(hijo, casa)]` |
| El profesor le explicó la lección a los alumnos | comunicacion | léxico | — | `do'(profesor, [explicar.to.(alumnos)'(profesor, lección)])` |
| **Juan le escribió una carta a su madre** | comunicacion | léxico | **True** | `do'(Juan, [escribir.to.(madre)'(Juan, carta)])` |
| **María le trajo café a su jefe** | transferencia | léxico | **True** | `[do'(María, Ø)] CAUSE [BECOME have'(jefe, café)]` |
| El niño le mostró el dibujo a su maestra | transferencia | léxico | — | `[do'(niño, Ø)] CAUSE [BECOME have'(maestra, dibujo)]` |
| Juan cocinó una cena para su familia | benefactiva | léxico | — | `[[do'(Juan, Ø)] CAUSE [BECOME have'(Juan, cena)]] PURP [have'(familia, cena)]` |

Verificado también: anidamiento con wrappers por fuera —
"Ayer le dio flores a María en el parque" →
`yesterday'(be-in'(parque, [[do'(x1, Ø)] CAUSE [BECOME have'(María, flores)]]))`
(coincide exacto con el ejemplo canónico del prompt); MISC lleva
`RRGVar=x3|RRGThemRel=Recipiente` en "María"; ningún caso pasa también por
`componer_cause` (no hay doble CAUSE, verificado); `ud2rrg` sigue fallando
igual con `obl:arg` (con o sin ditransitivas — es el bug ya documentado en
CHECKPOINT_L0_L2.md, L3).

**Hallazgo del checkpoint anterior corregido, no una regresión nueva:** el
prompt asume "ninguna de las 26 dianas de wrappers es ditransitiva" — falso
para 2 de las 7 frases agregadas en L1d específicamente para probar
wrappers (no son dianas históricas): **"Le compró un regalo a María"**
(comprar+dativo, es literalmente el mismo patrón de bug del reporte
original de Julian, solo con "comprar" en vez de "dar" — ahora
correctamente da `benefactiva`/PURP) y **"Le dije la verdad"** (ya era el
caso de prueba explícito de comunicación). Las otras 24 no se movieron
(verificado, `test_slow_26_dianas_casi_todas_sin_regresion`).

## 2. Léxico sembrado (`data/verbos_ditransitivos.xlsx`)

54 verbos: 22 transferencia (dar, entregar, regalar, enviar, mandar,
prestar, devolver, ofrecer, pagar, vender, conceder, otorgar, donar, pasar,
transferir, ceder, repartir, mostrar, enseñar, servir, alquilar, deber),
14 benefactiva (comprar, hacer, cocinar, preparar, construir, conseguir,
fabricar, dibujar, hornear, coser, reservar, elegir, buscar, pedir),
16 comunicación (decir, contar, explicar, preguntar, responder, contestar,
gritar, susurrar, comunicar, informar, anunciar, confesar, advertir,
prometer, recordar, escribir), + `traer`/`llevar` (no estaban en las listas
semilla del prompt pero SÍ en la nota de ambiguos — se agregaron
explícitamente con su plantilla default `transferencia`). 4 marcados
`ambiguo=True` con su nota: `escribir`, `recordar`, `traer`, `llevar` (ver
columna `notas` del xlsx para el razonamiento de cada uno, tal cual decisión
5 del prompt). Julian: este archivo es el que se edita para curar/expandir
— código intacto.

## 3. Candidatos logueados (`data/ditransitivos_candidatos.csv`)

Se creó durante esta sesión (no existía antes) al correr la batería de
arriba — 2 filas, ambas de disparos de verbos `ambiguo=True` (no de verbos
desconocidos, esos también se prueban en tests unitarios con
`garabatear` pero sobre un CSV temporal, no el real):

```
lema,oracion,plantilla
escribir,Juan le escribió una carta a su madre,comunicacion
traer,María le trajo café a su jefe,transferencia
```

Confirma el mecanismo de bootstrapping funciona: cuando Julian use
`gruxx_ai1.py` con oraciones reales, cada disparo de un verbo ambiguo o
desconocido quedará aquí para revisión/curaduría del xlsx.

## 4. Decisiones de implementación a confirmar (no re-litigadas, pero no
   100% especificadas en el prompt — juicio propio, documentado)

1. **`ls_type` de benefactiva = `accomplishment`**: el prompt dice
   explícitamente "Clase: causative accomplishment" para transferencia pero
   NO da una clase explícita para benefactiva. Inferí `accomplishment` por
   analogía (mismo núcleo `[do'(x,Ø)] CAUSE [BECOME have'(...)]`, telicidad
   compartida). Confirmar o corregir.
2. **Forma formal/léxica de comunicación**: el prompt da
   `do'(x1, [decir.to.(3sg)'(x1, verdad)])` como ejemplo único, mezclando
   una variable numerada (x1) con texto léxico (verdad, 3sg) en la misma
   cadena. Implementé una convención CONSISTENTE: x1/x2 numerados en la
   parte FORMAL (x,z — los dos únicos argumentos de la plantilla), y `y`
   (receptor) siempre embebido en el NOMBRE del predicado en ambas formas
   (no es un argumento numerado en esta plantilla simplificada). La parte
   LÉXICA sustituye x1/x2 por texto. Ver docstring de `construir_el` en
   `ditransitivas.py`. Confirmar que esta lectura es la intencionada.
3. **"basta el mapeo directo"**: implementé `cargar_continuum()` (lee de
   verdad `continuum_de_relaciones_tematicas.xlsx`) como validación/insumo,
   pero el lookup posición→rol que usan las 3 plantillas es una tabla FIJA
   hardcodeada (Efectuador/Recipiente/Tema, Emisor/Receptor/Contenido) —
   no un traversal genérico de `jerarquia_semantica_a_gramatical.xlsx`.
   Correcto para el alcance de este prompt; si la siguiente fase necesita
   MÁS posiciones/roles, ahí sí hará falta el traversal genérico.
4. **`RECIPIENTE` no está en el continuum de Julian**: el continuum lista
   "POSEEDOR" para el primer argumento de `pred'(x,y)`, no "RECIPIENTE" —
   ese viene de `jerarquia_semantica_a_gramatical.xlsx` (Given-to/Sent-to →
   Recipient). Y la jerarquía en inglés permite Recipient→Actor **o**
   Undergoer, pero aquí SIEMPRE mapea a NMR (decisión de L1a ya tomada: el
   dativo español no es macrorrol). Coherente con lo ya decidido, lo dejo
   anotado por si genera dudas al revisar el continuum.

## 5. Pendientes acumulados (explícitamente NO implementados, con TODO en código)

- **Forma plena de comunicación** (`do'(x, [express(α).to.(β).in.language.(γ)'(x,z)])`):
  la forma simple actual queda comentada como simplificación deliberada;
  refinar cuando Julian lo indique.
- **Fallback con probe BERTIN**: solo si el log de candidatos (`data/ditransitivos_candidatos.csv`)
  demuestra huecos reales tras uso — no implementado.
- **Bucle de corrección por el usuario** (auto-agregar al léxico curado
  cuando el usuario corrige una LS errónea en `gruxx_ai1.py`): comentario
  TODO dejado en el docstring de `ditransitivas.py`, sin implementar.
- Pendientes heredados de L0-L2 (sin resolver aún, listados en
  `CHECKPOINT_L0_L2.md` §5): bug de XPOS mayúsculas en `ud2rrg.py`,
  `obl:arg` fuera del dispatch de `ud2rrg.py`, compuestos "cerca de"/
  "delante de" con parseo inconsistente de Stanza, expansión de
  `_CASE_TEMPORAL`, diseño de wrapper de frecuencia.
