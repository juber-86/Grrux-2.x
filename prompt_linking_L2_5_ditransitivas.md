# Tarea: L2.5 — Estructuras Lógicas ditransitivas (recipiente) + relaciones temáticas por posición

Proyecto grrux (repo `~/proyectos/ud2rrg`). Python: `./venv/bin/python` (3.10). Entry point:
`python3 gruxx_ai1.py`. Etapa intermedia de la fase LINKING: va DESPUÉS de L0–L2 (ya completadas,
ver CHECKPOINT_L0_L2.md) y ANTES de L3/L4 — el checker de completeness de L4 necesita EL
ditransitivas correctas, y el AGX de L3 debe apuntar a un x_n verdadero.

**PROHIBIDO:** `ud2rrg.py` (es L3); `gruxx_ai1.py` COMPLETO esta vez (el dict del mapper ya fluye
por el render y el MISC existentes); clasificador (`predict.py`, `classifier.py`,
`decision_tree.py`), corroborador MLM, `pruebas_estructurales.py`, los `.joblib`,
`data/contextual_sentences.csv` — intactos. El VECTOR del clasificador nunca se toca (solo
override de plantilla/clase, mismo mecanismo que la causatividad del Paso 4).

## Motivación (bug real, reportado por Julian)

"Juan le dio flores a María" hoy produce una EL de plantilla Active Accomplishment:
`do'(juan, [dar'(juan, flores)]) & INGR consumed'(flores)` — ERRÓNEA. Los verbos con recipiente
son en RRG Realizaciones/Logros CAUSATIVOS y su EL une actividad + estado resultante de posesión.

## Decisiones de diseño de Julian (NO re-litigar)

1. **Los roles temáticos son POSICIONES en la EL, no etiquetas a clasificar.** No se usa ningún
   modelo/LLM en este prompt: el problema se descompone en (a) elegir la PLANTILLA de EL por
   verbo+construcción (léxico curado + trigger estructural + log de candidatos — el mismo patrón
   del léxico causativo), (b) mapear slots sintácticos → posiciones vía la jerarquía
   Actor-Undergoer, (c) etiquetar el rol por lookup de posición. Un probe BERTIN de fallback queda
   para el futuro SOLO si el log demuestra huecos reales.
2. **Plantillas** (metalenguaje inglés en primitivos, predicados léxicos en español):
   - TRANSFERENCIA ("Juan le dio un regalo a María"):
     `[do' (x, Ø)] CAUSE [BECOME have' (y, z)]` — x=efectuador, y=recipiente, z=tema.
     Clase: **causative accomplishment** (override léxico de clase, estilo `aktionsart_base`).
   - BENEFACTIVA/CREACIÓN-OBTENCIÓN ("Juan le compró un regalo a María", "le hice un pastel"):
     `[[do' (x, Ø)] CAUSE [BECOME have' (x, z)]] PURP [have' (y, z)]` — primero x obtiene/crea z,
     con propósito de que y lo posea. PURP es operador nuevo del builder.
   - COMUNICACIÓN ("le dije la verdad a Pedro"): **forma SIMPLE por ahora**:
     `do' (x, [<lema>.to.(y)' (x, z)])` (p.ej. `do' (yo, [decir.to.(Pedro)' (yo, verdad)])`).
     Dejar comentario en el código: es simplificación de la forma plena de Van Valin
     `do' (x, [express(α).to.(β).in.language.(γ)' (x, z)])` — refinar MUCHO después (orden
     explícita de Julian). Clase: activity (subtipo comunicación).
   - z puede ser `ccomp` en comunicación ("le dije que viniera" → z = la cláusula/su núcleo).
3. **El clítico/AGX no altera EL ni clase** (ya garantizado en L1): un solo x para el recipiente,
   venga como "le" solo (x = rasgos '3sg'), como "a María" sola, o doblado.
4. **Benefactiva SIN clítico incluida**: "compró un regalo para María" → misma plantilla PURP.
   Trigger: verbo del léxico benefactivo + obj + sintagma con case `para` (hoy periferia
   beneficiario). Al disparar, ese sintagma ASCIENDE de periferia a argumento y. Si el verbo NO
   está en el léxico benefactivo, "para X" queda en periferia listada como hoy (conservador).
5. **Léxico curado en xlsx** (Julian lo edita): sembrar
   `aspect_classifier/data/verbos_ditransitivos.xlsx` con columnas
   `lema | plantilla (transferencia|benefactiva|comunicacion) | ambiguo | notas`. Lista semilla
   (BORRADOR de Claude, aprobado para sembrar):
   - transferencia: dar, entregar, regalar, enviar, mandar, prestar, devolver, ofrecer, pagar,
     vender, conceder, otorgar, donar, pasar, transferir, ceder, repartir, mostrar, enseñar,
     servir, alquilar, deber.
   - benefactiva: comprar, hacer, cocinar, preparar, construir, conseguir, fabricar, dibujar,
     hornear, coser, reservar, elegir, buscar, pedir.
   - comunicacion: decir, contar, explicar, preguntar, responder, contestar, gritar, susurrar,
     comunicar, informar, anunciar, confesar, advertir, prometer, recordar, escribir.
   - AMBIGUOS conocidos (marcar `ambiguo=True`, default indicado, log cuando disparen): escribir
     (comunicación default; benefactiva "le escribió una carta"→transferencia posible), traer/
     llevar (transferencia default; benefactiva posible), recordar (comunicación default; psych
     State cuando no hay dativo — el clasificador manda si no dispara el trigger).
6. **Verbo fuera del léxico + trigger ditransitivo** → default `transferencia` + log a
   `data/ditransitivos_candidatos.csv` (mismo patrón que causative_candidates_heuristico).
7. **Futuro anotado, NO implementar**: bucle de corrección por el usuario (si gruxx genera una EL
   errónea, el usuario la corrige y el lema se agrega automáticamente al léxico curado). Dejar
   comentario TODO donde correspondería engancharlo.

## Trigger estructural (usa lo que L1 ya produce)

Construcción ditransitiva detectada cuando el root verbal tiene:
- argumento NMR(dativo) en core (obl:arg/iobj dativo, con o sin `agx`), **o** clítico dativo solo
  (`agx` con arg morfológico), **y** además obj (o ccomp para comunicación); **o**
- verbo en léxico benefactivo + obj + periferia con case `para` (decisión 4).
Sin trigger → nada cambia (transitivas/intransitivas siguen igual que hoy).

## Relaciones temáticas por posición (las tablas de Julian como DATOS)

- Cargar `aspect_classifier/data/continuum_de_relaciones_tematicas.xlsx` (5 columnas = 5
  posiciones de EL: arg-de-DO→AGENTE; 1er-arg-de-do'→EFECTUADOR/CREADOR/EMISOR/...;
  1er-arg-de-pred'(x,y)→POSEEDOR/PERCIBIDOR/...; 2º-arg-de-pred'(x,y)→TEMA/POSESIÓN/CONTENIDO/...;
  arg-de-pred'(x)→PACIENTE) y `jerarquia_semantica_a_gramatical.xlsx` (rutas
  Verb-specific→Thematic→Macrorole→GR). Derivar de ellas una tabla interna posición→rol.
- Para las plantillas de este prompt basta el mapeo directo: x (1er arg de do') = Efectuador →
  Actor; z (2º arg de have') = Tema → Undergoer; y (1er arg de have') = Recipiente → NMR.
  Comunicación: x = Emisor → Actor; z = Contenido → Undergoer; y = Receptor → NMR.
- `args_map` muestra el rol específico además del macropapel:
  `x1:Juan,nsubj,Actor(Efectuador); x2:regalo,obj,Undergoer(Tema); x3:María,obl:arg,NMR(Recipiente)`.
- MISC: añadir clave opcional `RRGThemRel=<rol>` al vocabulario de `misc_rrg.py` (documentar en el
  contrato del docstring — L3 podrá usarla).

## Integración en el mapper

- Módulo nuevo `aspect_classifier/ditransitivas.py` (funciones puras: detección de trigger,
  selección de plantilla, construcción de EL formal+léxica, asignación de roles por posición).
- Orden en `map_sentence_to_ls`: tras Etapa 1 y el clasificador, ANTES de los wrappers de
  periferia (los wrappers componen POR FUERA:
  "Ayer le dio flores a María en el parque" →
  `yesterday'(be-in'(parque, [[do'(x1, Ø)] CAUSE [BECOME have'(María, flores)]]))`).
- Si el trigger ditransitivo dispara, SU plantilla manda: no aplicar `componer_cause` encima (el
  CAUSE ya viene en la plantilla; documentar el orden respecto a la cascada de causatividad y
  añadir test de no-doble-CAUSE). El gate AA y las coerciones de pruebas_estructurales no aplican
  sobre la clase override (misma política que la causatividad léxica).
- Dict de retorno: `ls_type` = clase override, claves nuevas `ditransitiva`
  (plantilla/trigger/source) y roles específicos en args_map; `aspect_note` gana un segmento
  (`ditrans=transferencia(léxico)`).
- `config.yaml` sección `ditransitivas`: `enabled: true`, ruta del léxico, `default_plantilla:
  transferencia`, `benefactiva_para: true`. Con `enabled: false` → byte-idéntico a hoy
  (verificado programáticamente).

## Tests + validación

- Fríos (toks a mano, sin Stanza): "Juan le dio un regalo a María" → EL transferencia exacta,
  clase causative accomplishment, roles Efectuador/Tema/Recipiente, UN solo x3; "Juan le compró
  un regalo a María" → PURP; "compró un regalo para María" → PURP con ascenso del beneficiario;
  "compró un regalo" (sin dativo ni para) → transitiva normal SIN PURP; "Le dije la verdad"
  (clítico solo) → `do'(x1, [decir.to.(3sg)'(x1, verdad)])`; "le dije que viniera" → z=ccomp;
  verbo desconocido + dativo → default transferencia + fila en el log; verbo ambiguo → default +
  log; `enabled: false` → cero efecto.
- @slow (Stanza + pipeline): las oraciones de arriba end-to-end; las 26 dianas del informe de
  wrappers SIN regresión (ninguna es ditransitiva → no deben moverse); wrappers componen por
  fuera en la oración con periferia; el MISC lleva `RRGVar=x3` + `RRGThemRel=Recipiente` para
  María; árbol de ud2rrg NO cambia (sigue fallando con "le" — eso es L3, no intentar arreglarlo
  aquí).
- Suites previas verdes (nucleo_periferia, pruebas_estructurales 25/25, causatividad 9/9,
  complejo, pruebas_aspectuales 11/11, fase2_contextual 8/8, wrappers, misc).

## CHECKPOINT final — PARAR aquí

Informe para Julian: (1) EL nuevas de una batería ditransitiva (las de tests + 5-10 frases
variadas), (2) contenido sembrado del xlsx para su curaduría, (3) candidatos logueados si los
hubo, (4) pendientes acumulados (forma plena de comunicación, fallback probe si hay huecos,
bucle de corrección por usuario). L3 (capa `es` en ud2rrg: fix XPOS-tagset, obl:arg al dispatch,
AGX bajo NÚCLEO, leer MISC → peri() uniforme, guard nsubj-temporal "todos los días") y L4
(checker + KPI después) siguen tras esta revisión.
