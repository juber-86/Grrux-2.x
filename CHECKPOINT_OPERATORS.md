# CHECKPOINT — Etapa OPERATORS (operadores en la EL + proyección espejo)

Implementa `prompt_OPERATORS.md`. **Sin commits.** `ud2rrg.py` NO se tocó (los
operadores son una proyección aparte, no nodos del árbol). Clasificador,
corroborador MLM y `contextual_sentences.csv` intactos.

## 1. Salida de las oraciones de test

Terminal (`display_grr`, EL envuelta + línea `Operadores`; el detalle con estrato
y señal de origen sale con `--verbose`):

```
¿Ha estado llorando Juan?
  EL léxica  : ⟨IF INT ⟨TNS PRES ⟨ASP PERF PROG ⟨complet(do'(Juan, [llorar'(Juan)]))⟩⟩⟩⟩
  Operadores : IF=INT · TNS=PRES · ASP=PERF PROG
  IF    = INT       [clausular] ← signos de interrogación ¿?
  TNS   = PRES      [clausular] ← 'Ha' Tense=Pres
  ASP   = PERF PROG [nuclear]   ← auxiliar 'Ha' + auxiliar 'estado' + gerundio

Juan estudió.          ⟨IF DEC ⟨TNS PAST ⟨do'(Juan, [estudiar'(Juan)])⟩⟩⟩
Juan corría.           ⟨IF DEC ⟨TNS PAST ⟨ASP IMPF ⟨do'(Juan, [correr'(Juan)])⟩⟩⟩⟩
Juan no corrió.        ⟨IF DEC ⟨TNS PAST ⟨NEG ⟨no'([do'(Juan, [correr'(Juan)])])⟩⟩⟩⟩
Juan debe estudiar.    ⟨IF DEC ⟨TNS PRES ⟨MOD OBLG ⟨do'(Juan, [estudiar'(Juan)])⟩⟩⟩⟩
Quizá venga María.     ⟨IF DEC ⟨TNS PRES ⟨STA IRR ⟨maybe'([do'(María, [venir'(María)])])⟩⟩⟩⟩
¡Corre!                ⟨IF IMP ⟨TNS PRES ⟨do'(3sg, [correr'(3sg)])⟩⟩⟩
Juan está en la bibl.  ⟨IF DEC ⟨TNS PRES ⟨be-in'(biblioteca, Juan)⟩⟩⟩

Ayer Juan corrió tres horas en el parque.
  ⟨IF DEC ⟨TNS PAST ⟨yesterday'(be-in'(parque, [do'(Juan, [correr'(Juan, horas)])
                     & INGR consumed'(horas)]))⟩⟩⟩
```

El último confirma el anidamiento pedido: **wrappers de periferia por dentro,
operadores por fuera**.

El ejemplo canónico 2.26 se verifica BYTE A BYTE en
`test_canonico_2_26_envuelta_byte_a_byte`:
`⟨IF INT ⟨TNS PRES ⟨ASP PERF PROG ⟨do'(Juan, [llorar'(Juan)])⟩⟩⟩⟩`.

**Captura GUI** con la proyección activa: `captura_operadores_gui.png`
("Quizá Juan no deba estudiar mañana."). La espina baja desde la V del
predicado, en su misma x; NEG→NUC, MOD OBLG→CORE, IF/TNS/STA→CLAUSE.
(La herramienta de screenshot del entorno no respondía; la imagen es el SVG
que la propia GUI produce, rasterizado con inkscape.)

## 2. Tabla de detección — qué señal dispara cada operador

Todos los patrones se verificaron con una SONDA sobre Stanza español ANTES de
codificarlos (dos rondas, 30 oraciones). Hallazgos que cambiaron el diseño:

| Op | Señal | Nota de la sonda |
|---|---|---|
| **IF** DEC | por defecto | se muestra siempre (informativo) |
| **IF** INT | `PunctType=Qest` ¿?, o `PronType=Int` sin ¡! | — |
| **IF** IMP | `Mood=Imp`, **o** ¡! + raíz VERB finita **sin nsubj** | ⚠ Stanza **nunca** dio `Mood=Imp`: "¡Corre!" sale `Mood=Ind\|Person=3` y "¡Corred!" sale INTJ. IMP se infiere de la FORMA |
| **TNS** | `Tense` del **verbo finito** (raíz si es finita, si no el aux finito) | ⚠ crítico: en "habría estudiado" el participio raíz lleva `Tense=Past`; leerlo de ahí daría PAST cuando el tiempo real es condicional |
| **ASP** PERF | aux lema `haber` | — |
| **ASP** PROG | aux lema `estar` + raíz `VerbForm=Ger` | — |
| **ASP** IMPF | verbo finito `Tense=Imp` | imperfecto = TNS PAST **+** ASP IMPF |
| **NEG** | `advmod` con lema 'no' / `Polarity=Neg` | estrato nuclear por defecto (sin subtipo) |
| **MOD** OBLG/ABIL | aux `deber`/`poder` + raíz infinitiva | patrón limpio |
| **MOD** OBLG | raíz `tener` + `conj` infinitivo con `cc` 'que' | ⚠ "tener que" **no** parsea como auxiliar: la raíz es 'tiene' |
| **STA** IRR | verbo finito `Mood=Sub`/`Mood=Cnd`, o adverbio epistémico | "tal vez" es multipalabra (`fixed`), se resuelve uniendo el token y sus `fixed` |
| **STA** REAL | adverbio asertivo (lista aparte) | REAL se omite salvo que un adverbio lo haga explícito |

EVID / EVQ / DIR: no implementados (el español no los gramaticaliza), pero
conservan su hueco en `ORDEN_SCOPE` para que añadirlos no altere el anidamiento.

## 3. Perífrasis no cubiertas (logueadas)

`data/perifrasis_no_cubiertas.csv` (append-only, deduplicado):

```
soler,Juan suele correr por el parque .
querer,Juan quiere estudiar .
ir,Juan va a estudiar .
acabar,Juan acaba de llegar .
volver,Juan volvió a correr .
```

**Bug encontrado y corregido durante la validación:** la lista de vigiladas
estaba INERTE. Se buscaban solo dependientes `aux`, pero soler/querer/ir a/
acabar de/volver a parsean con el verbo de la perífrasis como **raíz** y el
infinitivo como `xcomp`. Se añadió ese segundo patrón; "Juan va al parque"
(sin infinitivo) sigue sin loguearse, para que el log sea señal y no ruido.

## 4. Regresión

- **Suite rápida completa: 295 passed, 28 skipped, 0 failed.**
- `--slow`: todo verde salvo **5 fallos PREEXISTENTES**, cada uno verificado
  reproduciendo con `operadores.enabled: false` (fallan idénticamente sin esta
  etapa):
  1. `test_l5::test_slow_correccion_ditransitiva_end_to_end` — `staging_lema_no_identificable` (bug ya documentado de `_lema_de` con ELs de solo do'/have'/CAUSE)
  2. `test_causatividad::test_slow_cause_por_clase_y_regresion`
  3. `test_fase2_contextual::test_slow_dianas_aa_y_controles`
  4. `test_pruebas_aspectuales::test_slow_blend_sube_pun`
  5. `test_gruxx_server::test_slow_corregir_el_real_con_reanalisis`
  (+ `test_gruxx_motor::test_estado_antes_de_cargar` falla **solo** si se corre
  después de la suite de servidor — artefacto de orden: pasa 23/23 aislado.)
- **Byte-idéntico con `enabled: false`** verificado en test dedicado
  (`test_slow_flag_maestro_apagado_es_byte_identico`): mismas `ls_formal`,
  `ls_lexical` y `ls_type`, y NINGUNA clave nueva en el dict.
- `ls_formal`/`ls_lexical` **nunca se tocan**: las envueltas viajan en claves
  nuevas (`ls_formal_ops`/`ls_lexical_ops`). Las dianas históricas no cambian
  de clase ni de EL interna.

## 5. TODO-OPERATORS-2 dejados

Tres puntos de enganche marcados en `aspect_classifier/correccion.py`:

1. **MENÚ** (`bucle_correccion`): opción "4) Un operador…". El insumo ya
   existe — `ls["operadores"]` trae valor + estrato + señal de origen.
2. **DESTINOS** (`_DESTINOS_ENRUTADO`): los operadores **no** son destino de
   enrutado (no son constituyentes). Necesitan destinos propios: valor,
   estrato, o "este operador no debería estar".
3. **RE-ANÁLISIS** (`_confirmar_persistencia`): el ciclo sirve, pero
   `confirma()` debe mirar `ls["operadores"]`. **Asimetría a decidir**: muchas
   correcciones de operador nacerán de un error de PARSE (el `Mood=Imp` que
   Stanza no da), y ahí no hay lexema que corregir sino una señal que anular —
   ¿léxico, override por oración, o ambos?

## 6. Dos redundancias que esta etapa deja a la vista (decisión de Julian)

No las toqué porque cambiarían la EL interna de dianas históricas, pero ahora
la misma información aparece dos veces:

1. **`complet(…)` / `prog(…)` vs `ASP PERF/PROG`** — `build_ls` ya envolvía la
   EL con esos modificadores: `⟨… ASP PERF PROG ⟨complet(do'(…))⟩…⟩`.
2. **`no'(…)` vs `NEG`** y **`maybe'(…)` vs `STA IRR`** — los wrappers de
   periferia tratan 'no' y los epistémicos como predicados de la EL.

En la teoría de Van Valin los operadores **no** son predicados de la EL, así
que lo ortodoxo sería quitarlos de ahí ahora que existen como operadores. Es
un cambio con regresión en las dianas: candidato natural para OPERATORS_2.

## 7. Archivos tocados

Nuevos: `aspect_classifier/operadores.py`, `aspect_classifier/test_operadores.py`,
`data/perifrasis_no_cubiertas.csv`, `captura_operadores_gui.png`.
Modificados: `rrg_ls_mapper.py` (import + `_anotar_operadores` + 2 returns),
`config.yaml` (sección `operadores`), `display_grr.py` (EL envuelta + líneas),
`gruxx_motor.py` (`_operadores_de` + contrato), `gui/{index.html,app.js,estilo.css}`,
`data/glosario_gruxx.csv` (categoría "Operadores", 10 entradas),
`correccion.py` (solo comentarios TODO-OPERATORS-2), `test_gruxx_motor.py`.
